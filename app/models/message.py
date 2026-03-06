"""
Model de mensagens (persistência para o painel admin).
"""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.config.database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_type = Column(String, nullable=False)  # 'admin' (bot/admin) or 'user'
    content = Column(Text, nullable=False)
    message_type = Column(String, nullable=False, default="text")  # text, image, audio
    status = Column(String, nullable=False, default="sent")  # sent, delivered, read
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")
