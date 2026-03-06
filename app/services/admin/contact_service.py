"""
Serviço de contatos (users) para o painel admin.
CRUD + listagem com subscription/plan aninhados.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from loguru import logger

from app.config.database import async_session
from app.models.user import User, LicenseType
from app.models.subscription import Subscription
from app.models.conversation import Conversation
from app.models.plan import Plan


class ContactService:
    """CRUD de contatos (mapeado sobre tabela users)."""

    async def get_all(
        self,
        search: Optional[str] = None,
        status: Optional[str] = None,
        page: int = 1,
        limit: int = 50,
    ) -> dict:
        """
        Lista contatos com subscription + plan aninhados.
        Suporta busca (name, phone, email) e filtro por status de assinatura.
        """
        async with async_session() as session:
            # Base query
            base_stmt = select(User).options(
                selectinload(User.subscription).selectinload(Subscription.plan)
            )

            # Filtro de busca
            if search:
                search_filter = f"%{search}%"
                base_stmt = base_stmt.where(
                    or_(
                        User.name.ilike(search_filter),
                        User.phone.ilike(search_filter),
                        User.email.ilike(search_filter),
                    )
                )

            # Filtro por status de assinatura
            if status:
                base_stmt = base_stmt.join(Subscription, Subscription.user_id == User.id).where(
                    Subscription.status == status
                )

            # Total count
            count_stmt = select(func.count()).select_from(base_stmt.subquery())
            count_result = await session.execute(count_stmt)
            total = count_result.scalar() or 0

            # Paginação
            offset = (page - 1) * limit
            stmt = base_stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
            result = await session.execute(stmt)
            users = result.scalars().unique().all()

            # Montar response com subscription + plan inline
            contacts = []
            for user in users:
                contact_data = {
                    "id": str(user.id),
                    "name": user.name,
                    "phone": user.phone,
                    "email": user.email,
                    "avatar_url": user.avatar_url,
                    "notes": user.notes or "",
                    "is_active": user.is_active,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at,
                    "subscription": None,
                    "plan": None,
                }
                if user.subscription:
                    contact_data["subscription"] = {
                        "id": str(user.subscription.id),
                        "plan_id": str(user.subscription.plan_id),
                        "status": user.subscription.status,
                        "started_at": user.subscription.started_at,
                        "expires_at": user.subscription.expires_at,
                        "canceled_at": user.subscription.canceled_at,
                        "created_at": user.subscription.created_at,
                    }
                    if user.subscription.plan:
                        contact_data["plan"] = {
                            "id": str(user.subscription.plan.id),
                            "name": user.subscription.plan.name,
                            "price": float(user.subscription.plan.price),
                            "billing_cycle": user.subscription.plan.billing_cycle,
                        }
                contacts.append(contact_data)

            return {
                "data": contacts,
                "total": total,
                "page": page,
                "limit": limit,
            }

    async def get_by_id(self, user_id: str) -> Optional[dict]:
        """
        Retorna um contato completo com subscription, plan, conversation e recent_messages.
        """
        async with async_session() as session:
            stmt = (
                select(User)
                .options(
                    selectinload(User.subscription).selectinload(Subscription.plan),
                    selectinload(User.conversation).selectinload(Conversation.messages),
                )
                .where(User.id == UUID(user_id))
            )
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return None

            contact_data = {
                "id": str(user.id),
                "name": user.name,
                "phone": user.phone,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "notes": user.notes or "",
                "is_active": user.is_active,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "subscription": None,
                "plan": None,
                "conversation": None,
                "recent_messages": [],
            }

            if user.subscription:
                contact_data["subscription"] = {
                    "id": str(user.subscription.id),
                    "plan_id": str(user.subscription.plan_id),
                    "status": user.subscription.status,
                    "started_at": user.subscription.started_at,
                    "expires_at": user.subscription.expires_at,
                    "canceled_at": user.subscription.canceled_at,
                    "created_at": user.subscription.created_at,
                }
                if user.subscription.plan:
                    contact_data["plan"] = {
                        "id": str(user.subscription.plan.id),
                        "name": user.subscription.plan.name,
                        "price": float(user.subscription.plan.price),
                        "billing_cycle": user.subscription.plan.billing_cycle,
                    }

            if user.conversation:
                contact_data["conversation"] = {
                    "id": str(user.conversation.id),
                    "status": user.conversation.status,
                    "last_message_at": user.conversation.last_message_at,
                    "created_at": user.conversation.created_at,
                }
                # Recent 3 messages
                msgs = sorted(user.conversation.messages, key=lambda m: m.created_at)
                recent = msgs[-3:] if len(msgs) > 3 else msgs
                contact_data["recent_messages"] = [
                    {
                        "id": str(m.id),
                        "sender_type": m.sender_type,
                        "content": m.content,
                        "message_type": m.message_type,
                        "status": m.status,
                        "created_at": m.created_at,
                    }
                    for m in recent
                ]

            return contact_data

    async def create(self, data: dict) -> dict:
        """Cria um novo contato (user)."""
        async with async_session() as session:
            # Check phone uniqueness
            existing = await session.execute(
                select(User).where(User.phone == data["phone_number"])
            )
            if existing.scalar_one_or_none():
                raise ValueError("CONFLICT:Contato com este telefone já existe")

            user = User(
                phone=data["phone_number"],
                name=data.get("name"),
                email=data.get("email"),
                avatar_url=data.get("avatar_url"),
                notes=data.get("notes", ""),
                is_active=data.get("is_active", True),
                license_type=LicenseType.FREE_TRIAL,
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            logger.info(f"Contact criado via admin: {user.phone} | ID: {user.id}")
            return {
                "id": str(user.id),
                "name": user.name,
                "phone": user.phone,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "notes": user.notes,
                "is_active": user.is_active,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
            }

    async def create_full(self, data: dict) -> dict:
        """
        Cria contato + subscription + conversation em uma única transação.
        Usado quando plan_id é fornecido no POST /contacts.
        """
        async with async_session() as session:
            # 1. Check phone uniqueness
            existing = await session.execute(
                select(User).where(User.phone == data["phone_number"])
            )
            if existing.scalar_one_or_none():
                raise ValueError("CONFLICT:Contato com este telefone já existe")

            # 2. Fetch plan
            plan = await session.get(Plan, UUID(data["plan_id"]))
            if not plan:
                raise ValueError("NOT_FOUND:Plano não encontrado")

            # 3. Determine license type from plan
            license_type = LicenseType.PRO if plan.billing_cycle != "free" else LicenseType.FREE_TRIAL

            # 4. Create user
            user = User(
                phone=data["phone_number"],
                name=data.get("name"),
                email=data.get("email"),
                avatar_url=data.get("avatar_url"),
                notes=data.get("notes", ""),
                is_active=True,
                license_type=license_type,
            )
            session.add(user)
            await session.flush()  # get user.id

            # 5. Create subscription with correct expiration
            now = datetime.utcnow()
            if plan.billing_cycle == "monthly":
                expires_at = now + timedelta(days=30)
            elif plan.billing_cycle == "yearly":
                expires_at = now + timedelta(days=365)
            else:
                expires_at = now + timedelta(days=7)  # free trial = 7 days

            sub_status = "active" if plan.billing_cycle != "free" else "trial"

            sub = Subscription(
                user_id=user.id,
                plan_id=plan.id,
                status=sub_status,
                started_at=now,
                expires_at=expires_at,
            )
            session.add(sub)

            # 6. Set license_expires_at on user (keeps bot working)
            user.license_expires_at = expires_at.date() if expires_at else None

            # 7. Create conversation (open, ready for admin to send messages)
            conv = Conversation(
                user_id=user.id,
                status="open",
            )
            session.add(conv)

            await session.commit()
            await session.refresh(user)
            await session.refresh(sub)
            await session.refresh(conv)

            logger.info(
                f"Contact completo criado via admin: {user.phone} | "
                f"Plan: {plan.name} | Sub: {sub.id} | Conv: {conv.id}"
            )

            return {
                "contact": {
                    "id": str(user.id),
                    "name": user.name,
                    "phone": user.phone,
                    "email": user.email,
                    "avatar_url": user.avatar_url,
                    "notes": user.notes,
                    "is_active": user.is_active,
                    "created_at": user.created_at,
                    "updated_at": user.updated_at,
                },
                "subscription": {
                    "id": str(sub.id),
                    "plan_id": str(sub.plan_id),
                    "plan_name": plan.name,
                    "status": sub.status,
                    "started_at": sub.started_at,
                    "expires_at": sub.expires_at,
                    "created_at": sub.created_at,
                },
                "conversation": {
                    "id": str(conv.id),
                    "contact_id": str(conv.user_id),
                    "status": conv.status,
                    "last_message_at": conv.last_message_at,
                    "created_at": conv.created_at,
                },
            }

    async def update(self, user_id: str, data: dict) -> Optional[dict]:
        """Atualiza um contato (PATCH parcial)."""
        async with async_session() as session:
            stmt = select(User).where(User.id == UUID(user_id))
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return None

            # Mapear phone_number → phone
            field_map = {"phone_number": "phone"}
            for key, value in data.items():
                if value is not None:
                    attr = field_map.get(key, key)
                    if hasattr(user, attr):
                        setattr(user, attr, value)

            await session.commit()
            await session.refresh(user)

            logger.info(f"Contact atualizado via admin: {user.phone} | ID: {user.id}")
            return {
                "id": str(user.id),
                "name": user.name,
                "phone": user.phone,
                "email": user.email,
                "avatar_url": user.avatar_url,
                "notes": user.notes,
                "is_active": user.is_active,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
            }

    async def delete(self, user_id: str) -> bool:
        """Remove um contato (e em cascata: subscription, conversation, messages)."""
        async with async_session() as session:
            stmt = select(User).where(User.id == UUID(user_id))
            result = await session.execute(stmt)
            user = result.scalar_one_or_none()

            if not user:
                return False

            await session.delete(user)
            await session.commit()

            logger.info(f"Contact removido via admin: {user.phone} | ID: {user_id}")
            return True
