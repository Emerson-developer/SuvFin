import uuid
from datetime import datetime, date
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, DateTime, Boolean, Enum, Date
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.config.database import Base


class LicenseType(PyEnum):
    FREE_TRIAL = "FREE_TRIAL"
    BASICO = "BASICO"
    PRO = "PRO"
    PREMIUM = "PREMIUM"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    license_type = Column(
        Enum(LicenseType), nullable=False, default=LicenseType.FREE_TRIAL
    )
    license_expires_at = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    abacatepay_customer_id = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    transactions = relationship("Transaction", back_populates="user", lazy="selectin")

    @property
    def is_license_valid(self) -> bool:
        """Verifica se a licença está ativa."""
        if self.license_type in (LicenseType.BASICO, LicenseType.PRO, LicenseType.PREMIUM):
            # Planos pagos: verificar expiração se houver
            if self.license_expires_at:
                return self.license_expires_at >= date.today()
            return True  # Sem data = válido
        if self.license_expires_at and self.license_expires_at >= date.today():
            return True
        return False

    @property
    def max_transactions(self) -> int | None:
        """Limite de transações por tipo de licença."""
        limits = {
            LicenseType.FREE_TRIAL: 50,
            LicenseType.BASICO: 100,
            LicenseType.PRO: None,   # Ilimitado
            LicenseType.PREMIUM: None,  # Ilimitado
        }
        return limits.get(self.license_type, 50)
