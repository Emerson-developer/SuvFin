"""
Model de pagamentos para rastreamento local.
"""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, DateTime, Integer, Enum, ForeignKey, Text
)
from sqlalchemy.dialects.postgresql import UUID

from app.config.database import Base


class PaymentStatus(PyEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


class BillingPeriod(PyEnum):
    MONTHLY = "MONTHLY"
    ANNUAL = "ANNUAL"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # AbacatePay IDs
    abacatepay_billing_id = Column(String(100), unique=True, nullable=False, index=True)
    abacatepay_customer_id = Column(String(100), nullable=True)

    # Plano e período
    plan_type = Column(String(20), nullable=True, default="PREMIUM")  # BASICO, PRO, PREMIUM
    billing_period = Column(String(20), nullable=True, default="MONTHLY")  # MONTHLY, ANNUAL

    # Valores
    amount_cents = Column(Integer, nullable=False)
    status = Column(
        Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING
    )
    payment_method = Column(String(20), default="PIX")
    payment_url = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    paid_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
