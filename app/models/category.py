import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.config.database import Base


# Categorias padrão do sistema
DEFAULT_CATEGORIES = [
    {"name": "Alimentação", "emoji": "🍔", "color": "#FF6B6B"},
    {"name": "Transporte", "emoji": "🚗", "color": "#4ECDC4"},
    {"name": "Moradia", "emoji": "🏠", "color": "#45B7D1"},
    {"name": "Saúde", "emoji": "🏥", "color": "#96CEB4"},
    {"name": "Educação", "emoji": "📚", "color": "#FFEAA7"},
    {"name": "Lazer", "emoji": "🎮", "color": "#DDA0DD"},
    {"name": "Vestuário", "emoji": "👕", "color": "#98D8C8"},
    {"name": "Serviços", "emoji": "⚡", "color": "#F7DC6F"},
    {"name": "Salário", "emoji": "💼", "color": "#82E0AA"},
    {"name": "Freelance", "emoji": "💻", "color": "#85C1E9"},
    {"name": "Investimentos", "emoji": "📈", "color": "#F8C471"},
    {"name": "Outros", "emoji": "📦", "color": "#AEB6BF"},
]


class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), nullable=False)
    emoji = Column(String(10), nullable=True, default="📦")
    color = Column(String(7), nullable=True, default="#AEB6BF")
    is_default = Column(Boolean, default=True)
    user_id = Column(UUID(as_uuid=True), nullable=True)  # null = global
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    transactions = relationship("Transaction", back_populates="category")
