import uuid
from datetime import datetime

from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.config.database import Base


class PluggyAccount(Base):
    """Conta bancária importada do Pluggy (corrente/poupança)."""

    __tablename__ = "pluggy_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pluggy_item_id = Column(
        UUID(as_uuid=True), ForeignKey("pluggy_items.id"), nullable=False, index=True
    )
    pluggy_account_id = Column(String(100), unique=True, nullable=False, index=True)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    name = Column(String(200), nullable=True)
    type = Column(String(50), nullable=False, default="BANK")
    subtype = Column(String(50), nullable=True)
    number = Column(String(50), nullable=True)
    balance = Column(Numeric(12, 2), nullable=True)
    currency_code = Column(String(10), default="BRL")
    profile = Column(String(2), nullable=False, default="PF", server_default="PF")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    item = relationship("PluggyItem", back_populates="accounts")
    transactions = relationship("PluggyTransaction", back_populates="account", lazy="selectin")
