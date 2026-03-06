"""
Schemas Pydantic para conversations (admin).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ConversationContactInline(BaseModel):
    id: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None

    model_config = {"from_attributes": True}


class LastMessageInline(BaseModel):
    id: str
    sender_type: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    """Conversation em listagens (GET /conversations)."""
    id: str
    contact_id: str  # maps to user_id
    status: str
    last_message_at: datetime
    created_at: datetime
    contact: Optional[ConversationContactInline] = None
    last_message: Optional[LastMessageInline] = None
    unread_count: int = 0

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    """Conversation detalhada (GET /conversations/:id)."""
    id: str
    contact_id: str
    status: str
    last_message_at: datetime
    created_at: datetime
    contact: Optional[dict] = None  # Full contact object
    plan: Optional[dict] = None
    subscription: Optional[dict] = None

    model_config = {"from_attributes": True}


class ConversationUpdate(BaseModel):
    status: str  # 'open' or 'closed'
