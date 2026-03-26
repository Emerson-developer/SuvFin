import uuid
from datetime import datetime

from sqlalchemy import Column, Integer, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.config.database import Base


class PluggyConnectionConfig(Base):
    """Controle de limites de conexões Open Finance por usuário."""

    __tablename__ = "pluggy_connection_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    max_connections = Column(Integer, nullable=False, default=2)
    active_connections = Column(Integer, nullable=False, default=0)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", backref="pluggy_connection_config", uselist=False)

    @property
    def can_create_connection(self) -> bool:
        return self.active_connections < self.max_connections
