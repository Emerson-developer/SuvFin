"""
Serviço de subscriptions para o painel admin.
CRUD + lógica de troca de plano + sincronização com users.license_type.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from loguru import logger

from app.config.database import async_session
from app.models.subscription import Subscription
from app.models.plan import Plan
from app.models.user import User, LicenseType


# Mapeamento billing_cycle → LicenseType
CYCLE_TO_LICENSE = {
    "free": LicenseType.FREE_TRIAL,
    "monthly": LicenseType.PRO,
    "yearly": LicenseType.PRO,
}


class SubscriptionService:
    """CRUD de subscriptions com sincronização user.license_type."""

    async def get_all(
        self,
        contact_id: Optional[str] = None,
        plan_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> list[dict]:
        """Lista subscriptions com filtros opcionais."""
        async with async_session() as session:
            stmt = select(Subscription)

            if contact_id:
                stmt = stmt.where(Subscription.user_id == UUID(contact_id))
            if plan_id:
                stmt = stmt.where(Subscription.plan_id == UUID(plan_id))
            if status:
                stmt = stmt.where(Subscription.status == status)

            result = await session.execute(stmt)
            subs = result.scalars().all()

            return [self._to_dict(s) for s in subs]

    async def get_by_contact(self, contact_id: str) -> Optional[dict]:
        """Retorna a subscription de um contato."""
        async with async_session() as session:
            stmt = select(Subscription).where(
                Subscription.user_id == UUID(contact_id)
            )
            result = await session.execute(stmt)
            sub = result.scalar_one_or_none()
            return self._to_dict(sub) if sub else None

    async def create(self, data: dict) -> dict:
        """Cria nova subscription e sincroniza com user.license_type."""
        async with async_session() as session:
            # Verificar se já existe
            existing = await session.execute(
                select(Subscription).where(
                    Subscription.user_id == UUID(data["contact_id"])
                )
            )
            if existing.scalar_one_or_none():
                raise ValueError("Contact already has a subscription")

            sub = Subscription(
                user_id=UUID(data["contact_id"]),
                plan_id=UUID(data["plan_id"]),
                status=data.get("status", "trial"),
                started_at=data.get("started_at") or datetime.now(timezone.utc),
                expires_at=data.get("expires_at"),
            )
            session.add(sub)
            await session.commit()
            await session.refresh(sub)

            # Sincronizar com user
            await self._sync_user_license(session, sub)

            logger.info(f"Subscription criada via admin: user={data['contact_id']}")
            return self._to_dict(sub)

    async def update(self, sub_id: str, data: dict) -> Optional[dict]:
        """
        Atualiza subscription.
        Se plan_id mudou: recalcular started_at e expires_at.
        Sincroniza com user.license_type.
        """
        async with async_session() as session:
            stmt = select(Subscription).where(Subscription.id == UUID(sub_id))
            result = await session.execute(stmt)
            sub = result.scalar_one_or_none()

            if not sub:
                return None

            plan_changed = False

            # Atualizar campos
            if data.get("plan_id") and str(sub.plan_id) != data["plan_id"]:
                sub.plan_id = UUID(data["plan_id"])
                plan_changed = True

            if data.get("status"):
                sub.status = data["status"]
                if data["status"] == "canceled":
                    sub.canceled_at = datetime.now(timezone.utc)

            if "expires_at" in data:
                sub.expires_at = data["expires_at"]

            if "canceled_at" in data:
                sub.canceled_at = data["canceled_at"]

            # Se plano mudou, recalcular datas
            if plan_changed:
                sub.started_at = datetime.now(timezone.utc)
                plan = await session.get(Plan, sub.plan_id)
                if plan:
                    if plan.billing_cycle == "monthly":
                        sub.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
                    elif plan.billing_cycle == "yearly":
                        sub.expires_at = datetime.now(timezone.utc) + timedelta(days=365)
                    else:  # free
                        sub.expires_at = None

            await session.commit()
            await session.refresh(sub)

            # Sincronizar com user
            await self._sync_user_license(session, sub)

            logger.info(f"Subscription atualizada via admin: {sub_id}")
            return self._to_dict(sub)

    async def _sync_user_license(self, session, sub: Subscription) -> None:
        """
        Sincroniza subscription → users.license_type e license_expires_at.
        Garante que o bot continua funcionando com a lógica existente.
        """
        try:
            user = await session.get(User, sub.user_id)
            if not user:
                return

            plan = await session.get(Plan, sub.plan_id)
            if not plan:
                return

            # Mapear billing_cycle → license_type
            license_type = CYCLE_TO_LICENSE.get(plan.billing_cycle, LicenseType.FREE_TRIAL)

            # Se cancelado, reverter para FREE_TRIAL
            if sub.status == "canceled":
                license_type = LicenseType.FREE_TRIAL

            user.license_type = license_type

            # Converter expires_at datetime → date para license_expires_at
            if sub.expires_at:
                user.license_expires_at = sub.expires_at.date() if hasattr(sub.expires_at, 'date') else sub.expires_at
            else:
                user.license_expires_at = None

            await session.commit()
            logger.debug(f"User license sincronizada: {user.phone} → {license_type.value}")
        except Exception as e:
            logger.error(f"Erro ao sincronizar user license: {e}")

    async def sync_from_payment(
        self,
        user_id: str,
        plan_type: str,
        billing_period: str,
    ) -> Optional[dict]:
        """
        Cria ou atualiza subscription quando um pagamento é confirmado.
        Chamado pelo webhook de pagamento para manter a tabela subscriptions sincronizada.

        plan_type: BASICO, PRO, PREMIUM (vindo do pagamento)
        billing_period: MONTHLY ou ANNUAL
        """
        try:
            async with async_session() as session:
                # Mapear plan_type + billing_period → plan UUID
                billing_cycle = "monthly" if billing_period == "MONTHLY" else "yearly"
                plan_stmt = select(Plan).where(Plan.billing_cycle == billing_cycle)
                plan_result = await session.execute(plan_stmt)
                plan = plan_result.scalar_one_or_none()

                if not plan:
                    logger.warning(
                        f"Plano não encontrado para cycle={billing_cycle}. "
                        f"Sync de subscription ignorado."
                    )
                    return None

                # Calcular expires_at
                now = datetime.now(timezone.utc)
                if billing_cycle == "monthly":
                    expires_at = now + timedelta(days=30)
                else:
                    expires_at = now + timedelta(days=365)

                # Buscar subscription existente
                sub_stmt = select(Subscription).where(
                    Subscription.user_id == UUID(user_id)
                )
                sub_result = await session.execute(sub_stmt)
                sub = sub_result.scalar_one_or_none()

                if sub:
                    # Atualizar subscription existente
                    sub.plan_id = plan.id
                    sub.status = "active"
                    sub.started_at = now
                    sub.expires_at = expires_at
                    sub.canceled_at = None
                else:
                    # Criar nova subscription
                    sub = Subscription(
                        user_id=UUID(user_id),
                        plan_id=plan.id,
                        status="active",
                        started_at=now,
                        expires_at=expires_at,
                    )
                    session.add(sub)

                await session.commit()
                await session.refresh(sub)

                logger.info(
                    f"Subscription sincronizada via pagamento: "
                    f"user={user_id}, plan={plan.name}, cycle={billing_cycle}"
                )
                return self._to_dict(sub)

        except Exception as e:
            logger.error(f"Erro ao sincronizar subscription via pagamento: {e}")
            return None

    @staticmethod
    def _to_dict(sub: Subscription) -> dict:
        return {
            "id": str(sub.id),
            "user_id": str(sub.user_id),
            "plan_id": str(sub.plan_id),
            "status": sub.status,
            "started_at": sub.started_at,
            "expires_at": sub.expires_at,
            "canceled_at": sub.canceled_at,
            "created_at": sub.created_at,
        }
