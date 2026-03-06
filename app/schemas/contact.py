"""
Schemas Pydantic para contacts (mapeados sobre users).
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


# --- Subscription inline (aninhado em Contact) ---

class SubscriptionInline(BaseModel):
    id: str
    plan_id: str
    status: str
    started_at: datetime
    expires_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PlanInline(BaseModel):
    id: str
    name: str
    price: float
    billing_cycle: str

    model_config = {"from_attributes": True}


# --- Contact responses ---

class ContactOut(BaseModel):
    """Contact retornado em listagens (GET /contacts)."""
    id: str
    name: Optional[str] = None
    phone_number: str = Field(alias="phone")
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    notes: Optional[str] = ""
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    subscription: Optional[SubscriptionInline] = None
    plan: Optional[PlanInline] = None

    model_config = {"from_attributes": True, "populate_by_name": True}


class ConversationInline(BaseModel):
    id: str
    status: str
    last_message_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class MessageInline(BaseModel):
    id: str
    sender_type: str
    content: str
    message_type: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ContactDetail(BaseModel):
    """Contact retornado em GET /contacts/:id (com subscription, plan, conversation, recent_messages)."""
    id: str
    name: Optional[str] = None
    phone_number: str = Field(alias="phone")
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    notes: Optional[str] = ""
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    subscription: Optional[SubscriptionInline] = None
    plan: Optional[PlanInline] = None
    conversation: Optional[ConversationInline] = None
    recent_messages: List[MessageInline] = []

    model_config = {"from_attributes": True, "populate_by_name": True}


# --- Contact create/update ---

class ContactCreate(BaseModel):
    name: str
    phone_number: str
    email: Optional[str] = None
    notes: Optional[str] = ""
    avatar_url: Optional[str] = None
    is_active: bool = True


class ContactUpdate(BaseModel):
    name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ContactListResponse(BaseModel):
    data: List[ContactOut]
    total: int
    page: int
    limit: int
