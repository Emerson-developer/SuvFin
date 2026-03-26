import uuid
from datetime import datetime, date as date_type

from sqlalchemy import Column, String, Numeric, Date, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.config.database import Base


class PluggyTransaction(Base):
    """Transação bancária importada do Pluggy Open Finance."""

    __tablename__ = "pluggy_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pluggy_account_id = Column(
        UUID(as_uuid=True), ForeignKey("pluggy_accounts.id"), nullable=False, index=True
    )
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    pluggy_transaction_id = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)
    description_raw = Column(String(500), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False)
    date = Column(Date, nullable=False, default=date_type.today)
    type = Column(String(20), nullable=False)  # DEBIT ou CREDIT
    status = Column(String(20), nullable=False, default="POSTED")  # POSTED ou PENDING
    category = Column(String(200), nullable=True)  # Categoria do Pluggy Enrichment
    category_id = Column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    payment_method = Column(String(50), nullable=True)  # PIX, TED, DOC, BOLETO
    currency_code = Column(String(10), default="BRL")
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    account = relationship("PluggyAccount", back_populates="transactions")
    suvfin_category = relationship("Category", lazy="selectin")
