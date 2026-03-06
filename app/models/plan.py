"""
Model de planos de assinatura.
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Numeric, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.config.database import Base


class Plan(Base):
    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    price = Column(Numeric(10, 2), nullable=False, default=0)
    features = Column(JSONB, nullable=False, default=list)
    billing_cycle = Column(String, nullable=False)  # 'free', 'monthly', 'yearly'
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="plan", lazy="selectin")
