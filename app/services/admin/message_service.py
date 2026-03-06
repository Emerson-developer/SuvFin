"""
Serviço de mensagens para o painel admin.
Listagem, criação (admin → user via WhatsApp), mark as read.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, and_, desc, update
from loguru import logger

from app.config.database import async_session
from app.models.message import Message


class MessageService:
    """Gerencia mensagens do painel admin."""

    async def get_by_conversation(
        self,
        conversation_id: str,
        limit: int = 100,
        before: Optional[datetime] = None,
    ) -> dict:
        """
        Lista mensagens de uma conversa (ASC, estilo WhatsApp).
        Suporta cursor-based pagination via `before`.
        """
        async with async_session() as session:
            stmt = select(Message).where(
                Message.conversation_id == UUID(conversation_id)
            )

            if before:
                stmt = stmt.where(Message.created_at < before)

            # +1 para detectar has_more
            stmt = stmt.order_by(desc(Message.created_at)).limit(limit + 1)

            result = await session.execute(stmt)
            messages = list(result.scalars().all())

            has_more = len(messages) > limit
            if has_more:
                messages = messages[:limit]

            # Reverter para ASC
            messages.reverse()

            return {
                "data": [
                    {
                        "id": str(m.id),
                        "conversation_id": str(m.conversation_id),
                        "sender_type": m.sender_type,
                        "content": m.content,
                        "message_type": m.message_type,
                        "status": m.status,
                        "created_at": m.created_at,
                    }
                    for m in messages
                ],
                "has_more": has_more,
            }

    async def create(
        self,
        conversation_id: str,
        content: str,
        sender_type: str = "admin",
        message_type: str = "text",
        status: str = "sent",
    ) -> dict:
        """
        Cria uma mensagem na conversa.
        Usado tanto pelo admin (sender_type='admin') quanto pelo dual-write (sender_type='user').
        """
        async with async_session() as session:
            msg = Message(
                conversation_id=UUID(conversation_id),
                sender_type=sender_type,
                content=content,
                message_type=message_type,
                status=status,
            )
            session.add(msg)
            await session.commit()
            await session.refresh(msg)

            return {
                "id": str(msg.id),
                "conversation_id": str(msg.conversation_id),
                "sender_type": msg.sender_type,
                "content": msg.content,
                "message_type": msg.message_type,
                "status": msg.status,
                "created_at": msg.created_at,
            }

    async def mark_as_read(self, conversation_id: str) -> int:
        """
        Marca todas as mensagens não lidas de uma conversa como lidas.
        Afeta apenas mensagens de sender_type='user' com status != 'read'.
        """
        async with async_session() as session:
            stmt = (
                update(Message)
                .where(
                    and_(
                        Message.conversation_id == UUID(conversation_id),
                        Message.sender_type == "user",
                        Message.status != "read",
                    )
                )
                .values(status="read")
            )
            result = await session.execute(stmt)
            await session.commit()

            count = result.rowcount
            logger.info(f"Marcadas {count} mensagens como lidas na conversa {conversation_id}")
            return count

    async def persist_bot_message(
        self,
        user_id: str,
        content: str,
        sender_type: str = "user",
        message_type: str = "text",
    ) -> Optional[dict]:
        """
        Persiste uma mensagem do bot/WhatsApp no PostgreSQL (dual-write).
        Cria a conversation se não existir.
        sender_type: 'user' para mensagens recebidas do user, 'admin' para respostas do bot.
        """
        try:
            from app.services.admin.conversation_service import ConversationService
            conv_service = ConversationService()
            conv = await conv_service.get_or_create(user_id)

            return await self.create(
                conversation_id=str(conv.id),
                content=content,
                sender_type=sender_type,
                message_type=message_type,
                status="delivered" if sender_type == "admin" else "sent",
            )
        except Exception as e:
            logger.error(f"Dual-write falhou para user {user_id}: {e}")
            return None
