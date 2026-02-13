import uuid
from datetime import datetime, date
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Numeric, Date, DateTime, ForeignKey, Enum, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.config.database import Base


class TransactionType(PyEnum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    type = Column(Enum(TransactionType), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    description = Column(String(255), nullable=True)
    date = Column(Date, nullable=False, default=date.today)
    category_id = Column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    receipt_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete

    # Relationships
    user = relationship("User", back_populates="transactions")
    category = relationship("Category", back_populates="transactions", lazy="selectin")

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
