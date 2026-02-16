"""
Serviço de licenciamento e gerenciamento de usuários.
"""

from datetime import date, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from loguru import logger

from app.config.database import async_session
from app.models.user import User, LicenseType


class LicenseService:
    """Gerencia licenças e validação de usuários."""

    async def validate_user(self, phone: str) -> Optional[User]:
        """Valida se o usuário existe e tem licença ativa. Retorna None se inválido."""
        async with async_session() as session:
            stmt = select(User).where(
                User.phone == phone,
                User.is_active.is_(True),
            )
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return None

            if not user.is_license_valid:
                logger.info(f"Licença expirada para {phone}")
                return None

            return user

    async def create_trial_user(self, phone: str, name: str = None) -> User:
        """Cria um novo usuário com trial de 7 dias."""
        async with async_session() as session:
            user = User(
                phone=phone,
                name=name,
                license_type=LicenseType.FREE_TRIAL,
                license_expires_at=date.today() + timedelta(days=7),
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            logger.info(f"Novo usuário trial criado: {phone} | ID: {user.id}")
            return user

    async def get_or_create_user(self, phone: str, name: str = None) -> tuple[User, bool]:
        """Busca usuário ou cria um novo com trial. Retorna (user, is_new)."""
        async with async_session() as session:
            stmt = select(User).where(User.phone == phone)
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if user:
                return user, False

        new_user = await self.create_trial_user(phone, name)
        return new_user, True

    async def upgrade_to_plan(
        self,
        user_id: str,
        plan: str = "PRO",
        period: str = "MONTHLY",
        abacatepay_customer_id: str = None,
    ) -> bool:
        """Faz upgrade da licença para o plano escolhido."""
        from datetime import timedelta

        plan_map = {
            "BASICO": LicenseType.BASICO,
            "PRO": LicenseType.PRO,
            "PREMIUM": LicenseType.PREMIUM,
        }
        license_type = plan_map.get(plan.upper(), LicenseType.PRO)

        async with async_session() as session:
            stmt = select(User).where(User.id == UUID(user_id))
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return False

            user.license_type = license_type

            # Definir expiração baseada no período
            if period.upper() == "ANNUAL":
                user.license_expires_at = date.today() + timedelta(days=365)
            else:
                user.license_expires_at = date.today() + timedelta(days=30)

            if abacatepay_customer_id:
                user.abacatepay_customer_id = abacatepay_customer_id

            await session.commit()
            logger.info(f"Upgrade para {plan} ({period}): {user.phone}")
            return True

    async def upgrade_to_premium(
        self, user_id: str, abacatepay_customer_id: str = None
    ) -> bool:
        """Legado: redireciona para upgrade_to_plan com PRO."""
        return await self.upgrade_to_plan(
            user_id=user_id,
            plan="PRO",
            period="MONTHLY",
            abacatepay_customer_id=abacatepay_customer_id,
        )

    # Links fixos de pagamento pré-criados no AbacatePay
    PAYMENT_LINKS = {
        ("BASICO", "MONTHLY"): "https://app.abacatepay.com/pay/bill_ugcAJz0p6j0Bmz4FSeBPEEdh",
        ("BASICO", "ANNUAL"): "https://app.abacatepay.com/pay/bill_HUMtfuQQ4yTga0bXDrdx5aFq",
        ("PRO", "MONTHLY"): "https://app.abacatepay.com/pay/bill_bLp1mFcbztXSqZBgy2dQtSQK",
        ("PRO", "ANNUAL"): "https://app.abacatepay.com/pay/bill_mMYEMuYcXUWt0gLwyED2GrnM",
        ("PREMIUM", "MONTHLY"): "https://app.abacatepay.com/pay/bill_aPmMZjhfECMXhfWBtUrWsa1T",
        ("PREMIUM", "ANNUAL"): "https://app.abacatepay.com/pay/bill_phz1JkKGHP4FHLsbYhfXTAF6",
    }

    async def get_payment_link(self, phone: str, plan: str = "PRO", period: str = "MONTHLY") -> str:
        """
        Retorna o link de pagamento fixo do AbacatePay para o plano selecionado.
        """
        plan = plan.upper()
        period = period.upper()

        url = self.PAYMENT_LINKS.get((plan, period))
        if not url:
            raise ValueError(f"Plano inválido: {plan} {period}")

        logger.info(f"💳 Link de pagamento para {phone}: {plan} {period} → {url}")
        return url

    async def check_transaction_limit(self, user_id: str) -> dict:
        """Verifica se o usuário atingiu o limite de transações (trial)."""
        from sqlalchemy import func
        from app.models.transaction import Transaction

        async with async_session() as session:
            stmt = select(User).where(User.id == UUID(user_id))
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return {"allowed": False, "reason": "Usuário não encontrado."}

            max_tx = user.max_transactions
            if max_tx is None:
                return {"allowed": True}  # Premium

            # Contar transações
            count_stmt = select(func.count(Transaction.id)).where(
                Transaction.user_id == UUID(user_id),
                Transaction.deleted_at.is_(None),
            )
            count_result = await session.execute(count_stmt)
            current_count = count_result.scalar() or 0

            if current_count >= max_tx:
                return {
                    "allowed": False,
                    "reason": (
                        f"Você atingiu o limite de {max_tx} lançamentos do seu plano. "
                        f"Faça upgrade para desbloquear mais! 🚀\n\n"
                        f"⚡ *Pro* — R$ 19,90/mês (ilimitado)\n"
                        f"👑 *Premium* — R$ 34,90/mês (ilimitado + IA)\n\n"
                        f"Envie _\"Quero fazer upgrade\"_ para ver as opções!"
                    ),
                    "current": current_count,
                    "limit": max_tx,
                }

            return {
                "allowed": True,
                "current": current_count,
                "limit": max_tx,
                "remaining": max_tx - current_count,
            }
