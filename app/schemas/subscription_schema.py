"""
Schemas Pydantic para subscriptions (admin).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SubscriptionOut(BaseModel):
    id: str
    user_id: str
    plan_id: str
    status: str
    started_at: datetime
    expires_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SubscriptionCreate(BaseModel):
    contact_id: str  # maps to user_id
    plan_id: str
    status: str = "trial"
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class SubscriptionUpdate(BaseModel):
    plan_id: Optional[str] = None
    status: Optional[str] = None
    expires_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None
