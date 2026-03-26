"""
Schemas Pydantic para Pluggy Open Finance.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Webhook payload do Pluggy
# ------------------------------------------------------------------

class PluggyWebhookEvent(BaseModel):
    """Payload genérico de evento webhook do Pluggy."""
    event: str = Field(..., description="Tipo do evento: item/created, item/updated, etc.")
    itemId: Optional[str] = None
    triggeredBy: Optional[str] = None

    # Campos de transactions/created
    createdTransactionsLink: Optional[str] = None

    # Campos de transactions/updated e deleted
    transactionIds: Optional[list[str]] = None


# ------------------------------------------------------------------
# Respostas da API Pluggy routes
# ------------------------------------------------------------------

class PluggyConnectResponse(BaseModel):
    """Resposta ao gerar um connect token."""
    connect_url: str
    expires_in_minutes: int = 30


class PluggyAccountResponse(BaseModel):
    """Conta bancária conectada."""
    id: str
    bank_name: Optional[str] = None
    account_name: Optional[str] = None
    subtype: Optional[str] = None
    number: Optional[str] = None
    balance: Optional[Decimal] = None
    currency_code: str = "BRL"
    last_sync_at: Optional[datetime] = None
    status: str = "UPDATED"


class PluggyTransactionResponse(BaseModel):
    """Transação importada do Pluggy."""
    id: str
    description: Optional[str] = None
    amount: Decimal
    date: date
    type: str  # DEBIT ou CREDIT
    status: str  # POSTED ou PENDING
    category: Optional[str] = None
    payment_method: Optional[str] = None


# ------------------------------------------------------------------
# Admin schemas
# ------------------------------------------------------------------

class PluggyConnectionConfigResponse(BaseModel):
    """Config de conexão do usuário (admin view)."""
    user_id: str
    user_phone: Optional[str] = None
    user_name: Optional[str] = None
    max_connections: int
    active_connections: int
    notes: Optional[str] = None

    model_config = {"from_attributes": True}


class PluggyConnectionConfigUpdate(BaseModel):
    """Atualização de config pelo admin."""
    max_connections: Optional[int] = Field(None, ge=0, le=50)
    notes: Optional[str] = None
