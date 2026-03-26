import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Integer, DateTime, Boolean, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.config.database import Base


class PluggyItem(Base):
    """Conexão bancária do usuário via Pluggy Open Finance."""

    __tablename__ = "pluggy_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    pluggy_item_id = Column(String(100), unique=True, nullable=False, index=True)
    connector_name = Column(String(200), nullable=True)
    connector_id = Column(Integer, nullable=True)
    status = Column(String(50), nullable=False, default="UPDATING")
    is_active = Column(Boolean, default=True)
    last_sync_at = Column(DateTime, nullable=True)
    consent_expires_at = Column(DateTime, nullable=True)
    connected_at = Column(DateTime, default=datetime.utcnow)
    disconnected_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="pluggy_items")
    accounts = relationship("PluggyAccount", back_populates="item", lazy="selectin")
