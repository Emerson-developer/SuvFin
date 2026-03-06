"""
Schemas Pydantic para dashboard stats (admin).
"""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel


class PlanDistribution(BaseModel):
    plan_id: str
    plan_name: str
    count: int


class InactiveContact(BaseModel):
    contact_id: str
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    last_user_message_at: Optional[datetime] = None
    level: str  # 'active', 'warning', 'critical', 'never'


class RecentConversation(BaseModel):
    id: str
    contact_id: str
    contact_name: Optional[str] = None
    contact_avatar: Optional[str] = None
    last_message_at: datetime
    last_message_content: Optional[str] = None
    unread_count: int = 0
    inactivity_level: str = "active"


class DashboardStats(BaseModel):
    total_contacts: int = 0
    active_contacts: int = 0
    open_conversations: int = 0
    messages_today: int = 0
    past_due_subscriptions: int = 0
    trial_subscriptions: int = 0
    plan_distribution: List[PlanDistribution] = []
    inactive_contacts: List[InactiveContact] = []
    recent_open_conversations: List[RecentConversation] = []
