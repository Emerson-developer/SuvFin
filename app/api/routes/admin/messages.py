"""
Rotas de messages.
GET   /api/v1/admin/messages?conversation_id=...
POST  /api/v1/admin/messages
PATCH /api/v1/admin/messages/read
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status

from app.api.middleware.auth import get_current_admin
from app.schemas.message_schema import MessageCreate, MarkMessagesReadRequest
from app.services.admin.message_service import MessageService
from app.services.whatsapp.client import WhatsAppClient
from app.services.admin.conversation_service import ConversationService

router = APIRouter(prefix="/messages", tags=["admin-messages"])


@router.get("")
async def list_messages(
    conversation_id: str = Query(..., description="ID da conversa"),
    limit: int = Query(100, ge=1, le=500),
    before: Optional[datetime] = Query(None, description="Cursor: mensagens anteriores a esta data"),
    _admin: dict = Depends(get_current_admin),
):
    """
    Lista mensagens de uma conversa (ASC, estilo WhatsApp).
    Cursor-based pagination via `before`.
    """
    service = MessageService()
    result = await service.get_by_conversation(
        conversation_id=conversation_id,
        limit=limit,
        before=before,
    )
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
async def send_message(
    body: MessageCreate,
    _admin: dict = Depends(get_current_admin),
):
    """
    Envia mensagem como admin.
    Persiste no banco + envia via WhatsApp para o user.
    """
    # Persistir a mensagem
    msg_service = MessageService()
    message = await msg_service.create(
        conversation_id=body.conversation_id,
        content=body.content,
        sender_type="admin",
        message_type=body.message_type,
    )

    # Enviar via WhatsApp
    try:
        conv_service = ConversationService()
        conv = await conv_service.get_by_id(body.conversation_id)
        if conv and conv.get("contact"):
            phone = conv["contact"].get("phone")
            if phone:
                client = WhatsAppClient()
                await client.send_text(phone, body.content)
    except Exception as e:
        from loguru import logger
        logger.error(f"Falha ao enviar mensagem via WhatsApp: {e}")
        # Mensagem já está persistida, não falhar

    return {"data": message}


@router.patch("/read")
async def mark_messages_read(
    body: MarkMessagesReadRequest,
    _admin: dict = Depends(get_current_admin),
):
    """
    Marca todas as mensagens não lidas de uma conversa como lidas.
    Afeta apenas mensagens de sender_type='user' com status != 'read'.
    """
    service = MessageService()
    count = await service.mark_as_read(body.conversation_id)
    return {"updated_count": count}
