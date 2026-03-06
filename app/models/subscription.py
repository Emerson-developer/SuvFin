"""
Model de assinaturas (vínculo user ↔ plan).
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.config.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    plan_id = Column(
        UUID(as_uuid=True),
        ForeignKey("plans.id"),
        nullable=False,
    )
    status = Column(String, nullable=False, default="trial")  # active, canceled, past_due, trial
    started_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="subscription", lazy="selectin")
    plan = relationship("Plan", back_populates="subscriptions", lazy="selectin")
