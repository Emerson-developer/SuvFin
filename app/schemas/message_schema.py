"""
Schemas Pydantic para messages (admin).
"""

from datetime import datetime
from typing import List

from pydantic import BaseModel


class MessageOut(BaseModel):
    id: str
    conversation_id: str
    sender_type: str
    content: str
    message_type: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageCreate(BaseModel):
    conversation_id: str
    content: str
    message_type: str = "text"


class MarkMessagesReadRequest(BaseModel):
    conversation_id: str


class MarkMessagesReadResponse(BaseModel):
    updated_count: int


class MessageListResponse(BaseModel):
    data: List[MessageOut]
    has_more: bool
