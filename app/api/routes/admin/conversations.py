"""
Rotas de conversations.
GET   /api/v1/admin/conversations
GET   /api/v1/admin/conversations/{conv_id}
GET   /api/v1/admin/conversations/by-contact/{contact_id}
PATCH /api/v1/admin/conversations/{conv_id}
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.middleware.auth import get_current_admin
from app.schemas.conversation_schema import ConversationUpdate
from app.services.admin.conversation_service import ConversationService

router = APIRouter(prefix="/conversations", tags=["admin-conversations"])


@router.get("")
async def list_conversations(
    status_filter: str = Query(None, alias="status"),
    search: str = Query(None),
    _admin: dict = Depends(get_current_admin),
):
    """
    Lista conversas com contact, last_message e unread_count.
    Ordenadas por last_message_at DESC.
    """
    service = ConversationService()
    conversations = await service.get_all(
        status=status_filter,
        search=search,
    )
    return {"data": conversations}


@router.get("/by-contact/{contact_id}")
async def get_conversation_by_contact(
    contact_id: str,
    _admin: dict = Depends(get_current_admin),
):
    """Retorna a conversa de um contato."""
    service = ConversationService()
    conv = await service.get_by_contact(contact_id)
    return {"data": conv}


@router.get("/{conv_id}")
async def get_conversation(
    conv_id: str,
    _admin: dict = Depends(get_current_admin),
):
    """Retorna conversa com contact, plan e subscription."""
    service = ConversationService()
    conv = await service.get_by_id(conv_id)

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"data": conv}


@router.patch("/{conv_id}")
async def update_conversation(
    conv_id: str,
    body: ConversationUpdate,
    _admin: dict = Depends(get_current_admin),
):
    """Altera status da conversa (open/closed)."""
    if body.status not in ("open", "closed"):
        raise HTTPException(status_code=422, detail="Status must be 'open' or 'closed'")

    service = ConversationService()
    conv = await service.update_status(conv_id, body.status)

    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {"data": conv}
