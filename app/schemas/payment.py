"""
Schemas Pydantic para pagamentos (AbacatePay).
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------

class BillingStatus(str, PyEnum):
    PENDING = "PENDING"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    PAID = "PAID"
    REFUNDED = "REFUNDED"


class PaymentMethod(str, PyEnum):
    PIX = "PIX"


class BillingFrequency(str, PyEnum):
    ONE_TIME = "ONE_TIME"


# ------------------------------------------------------------------
# Request schemas
# ------------------------------------------------------------------

class CreateBillingRequest(BaseModel):
    """Request para gerar link de pagamento do Premium."""
    phone: str = Field(..., description="Número do WhatsApp do usuário")
    email: Optional[str] = Field(None, description="E-mail do cliente (opcional)")
    name: Optional[str] = Field(None, description="Nome do cliente (opcional)")
    tax_id: Optional[str] = Field(None, description="CPF/CNPJ do cliente (opcional)")


# ------------------------------------------------------------------
# Webhook schemas (payload vindo do AbacatePay)
# ------------------------------------------------------------------

class AbacatePayCustomerMetadata(BaseModel):
    name: Optional[str] = None
    cellphone: Optional[str] = None
    email: Optional[str] = None
    tax_id: Optional[str] = Field(None, alias="taxId")

    model_config = {"populate_by_name": True}


class AbacatePayCustomer(BaseModel):
    id: str
    metadata: AbacatePayCustomerMetadata


class AbacatePayProduct(BaseModel):
    id: str
    external_id: Optional[str] = Field(None, alias="externalId")
    quantity: int = 1

    model_config = {"populate_by_name": True}


class AbacatePayBillingMetadata(BaseModel):
    fee: Optional[int] = None
    return_url: Optional[str] = Field(None, alias="returnUrl")
    completion_url: Optional[str] = Field(None, alias="completionUrl")

    model_config = {"populate_by_name": True}


class AbacatePayBilling(BaseModel):
    """Estrutura de uma cobrança retornada pelo AbacatePay."""
    id: str
    frequency: BillingFrequency = BillingFrequency.ONE_TIME
    url: str
    amount: int  # em centavos
    status: BillingStatus
    dev_mode: bool = Field(False, alias="devMode")
    methods: list[PaymentMethod] = [PaymentMethod.PIX]
    products: list[AbacatePayProduct] = []
    customer: Optional[AbacatePayCustomer] = None
    metadata: Optional[AbacatePayBillingMetadata] = None
    next_billing: Optional[str] = Field(None, alias="nextBilling")
    created_at: Optional[str] = Field(None, alias="createdAt")
    updated_at: Optional[str] = Field(None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class AbacatePayWebhookPayload(BaseModel):
    """Payload que o AbacatePay envia no webhook."""
    data: AbacatePayBilling


# ------------------------------------------------------------------
# Response schemas
# ------------------------------------------------------------------

class CreateBillingResponse(BaseModel):
    """Resposta ao criar um link de pagamento."""
    billing_id: str
    payment_url: str
    amount_cents: int
    status: str
    message: str


class PaymentStatusResponse(BaseModel):
    """Resposta de status do pagamento."""
    user_phone: str
    license_type: str
    is_premium: bool
    billing_id: Optional[str] = None
    billing_status: Optional[str] = None
