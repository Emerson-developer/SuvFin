"""
Serviço de conversas para o painel admin.
Listagem com unread_count, last_message, contact inline.
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select, func, and_, desc
from sqlalchemy.orm import selectinload
from loguru import logger

from app.config.database import async_session
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.user import User
from app.models.subscription import Subscription


class ConversationService:
    """Gerencia conversas do painel admin."""

    async def get_all(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> list[dict]:
        """
        Lista conversas com contact inline, last_message e unread_count.
        Ordenadas por last_message_at DESC.
        """
        async with async_session() as session:
            stmt = (
                select(Conversation)
                .options(selectinload(Conversation.user))
                .order_by(desc(Conversation.last_message_at))
            )

            if status:
                stmt = stmt.where(Conversation.status == status)

            if search:
                stmt = stmt.join(User, User.id == Conversation.user_id).where(
                    User.name.ilike(f"%{search}%")
                )

            result = await session.execute(stmt)
            conversations = result.scalars().unique().all()

            items = []
            for conv in conversations:
                # Last message
                last_msg_stmt = (
                    select(Message)
                    .where(Message.conversation_id == conv.id)
                    .order_by(desc(Message.created_at))
                    .limit(1)
                )
                last_msg_result = await session.execute(last_msg_stmt)
                last_msg = last_msg_result.scalar_one_or_none()

                # Unread count
                unread_stmt = select(func.count(Message.id)).where(
                    and_(
                        Message.conversation_id == conv.id,
                        Message.sender_type == "user",
                        Message.status != "read",
                    )
                )
                unread_result = await session.execute(unread_stmt)
                unread_count = unread_result.scalar() or 0

                # Search in last_message content
                if search and last_msg:
                    if search.lower() not in (last_msg.content or "").lower():
                        if not conv.user or search.lower() not in (conv.user.name or "").lower():
                            continue

                item = {
                    "id": str(conv.id),
                    "contact_id": str(conv.user_id),
                    "status": conv.status,
                    "last_message_at": conv.last_message_at,
                    "created_at": conv.created_at,
                    "contact": None,
                    "last_message": None,
                    "unread_count": unread_count,
                }

                if conv.user:
                    item["contact"] = {
                        "id": str(conv.user.id),
                        "name": conv.user.name,
                        "avatar_url": conv.user.avatar_url,
                    }

                if last_msg:
                    item["last_message"] = {
                        "id": str(last_msg.id),
                        "sender_type": last_msg.sender_type,
                        "content": last_msg.content,
                        "created_at": last_msg.created_at,
                    }

                items.append(item)

            return items

    async def get_by_id(self, conv_id: str) -> Optional[dict]:
        """Retorna conversa com contact, plan e subscription."""
        async with async_session() as session:
            stmt = (
                select(Conversation)
                .options(
                    selectinload(Conversation.user)
                    .selectinload(User.subscription)
                    .selectinload(Subscription.plan)
                )
                .where(Conversation.id == UUID(conv_id))
            )
            result = await session.execute(stmt)
            conv = result.scalar_one_or_none()

            if not conv:
                return None

            data = {
                "id": str(conv.id),
                "contact_id": str(conv.user_id),
                "status": conv.status,
                "last_message_at": conv.last_message_at,
                "created_at": conv.created_at,
                "contact": None,
                "plan": None,
                "subscription": None,
            }

            if conv.user:
                data["contact"] = {
                    "id": str(conv.user.id),
                    "name": conv.user.name,
                    "phone": conv.user.phone,
                    "email": conv.user.email,
                    "avatar_url": conv.user.avatar_url,
                    "is_active": conv.user.is_active,
                }
                if conv.user.subscription:
                    sub = conv.user.subscription
                    data["subscription"] = {
                        "id": str(sub.id),
                        "plan_id": str(sub.plan_id),
                        "status": sub.status,
                        "started_at": sub.started_at,
                        "expires_at": sub.expires_at,
                    }
                    if sub.plan:
                        data["plan"] = {
                            "id": str(sub.plan.id),
                            "name": sub.plan.name,
                            "price": float(sub.plan.price),
                            "billing_cycle": sub.plan.billing_cycle,
                        }

            return data

    async def get_by_contact(self, contact_id: str) -> Optional[dict]:
        """Retorna conversa de um contato."""
        async with async_session() as session:
            stmt = select(Conversation).where(
                Conversation.user_id == UUID(contact_id)
            )
            result = await session.execute(stmt)
            conv = result.scalar_one_or_none()

            if not conv:
                return None

            return {
                "id": str(conv.id),
                "contact_id": str(conv.user_id),
                "status": conv.status,
                "last_message_at": conv.last_message_at,
                "created_at": conv.created_at,
            }

    async def update_status(self, conv_id: str, status: str) -> Optional[dict]:
        """Altera status da conversa (open/closed)."""
        async with async_session() as session:
            stmt = select(Conversation).where(Conversation.id == UUID(conv_id))
            result = await session.execute(stmt)
            conv = result.scalar_one_or_none()

            if not conv:
                return None

            conv.status = status
            await session.commit()
            await session.refresh(conv)

            return {
                "id": str(conv.id),
                "contact_id": str(conv.user_id),
                "status": conv.status,
                "last_message_at": conv.last_message_at,
                "created_at": conv.created_at,
            }

    async def get_or_create(self, user_id: str) -> Conversation:
        """
        Obtém ou cria conversa para um user.
        Usado pelo dual-write de mensagens.
        """
        async with async_session() as session:
            stmt = select(Conversation).where(
                Conversation.user_id == UUID(user_id)
            )
            result = await session.execute(stmt)
            conv = result.scalar_one_or_none()

            if conv:
                return conv

            conv = Conversation(
                user_id=UUID(user_id),
                status="open",
            )
            session.add(conv)
            await session.commit()
            await session.refresh(conv)

            logger.info(f"Conversation criada para user: {user_id}")
            return conv
