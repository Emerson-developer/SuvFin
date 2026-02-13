from pydantic import BaseModel
from typing import Optional
from datetime import date, datetime
from uuid import UUID
from enum import Enum


class TransactionTypeEnum(str, Enum):
    INCOME = "INCOME"
    EXPENSE = "EXPENSE"


class TransactionCreate(BaseModel):
    type: TransactionTypeEnum
    amount: float
    description: Optional[str] = None
    date: date = None
    category_name: Optional[str] = None
    receipt_url: Optional[str] = None


class TransactionUpdate(BaseModel):
    amount: Optional[float] = None
    description: Optional[str] = None
    date: Optional[date] = None
    category_name: Optional[str] = None


class TransactionResponse(BaseModel):
    id: UUID
    type: str
    amount: float
    description: Optional[str]
    date: date
    category_name: Optional[str] = None
    category_emoji: Optional[str] = None
    receipt_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReportPeriod(BaseModel):
    start_date: date
    end_date: date


class ReportSummary(BaseModel):
    period_label: str
    total_income: float
    total_expense: float
    balance: float
    by_category: list[dict]
    transaction_count: int


class ReceiptData(BaseModel):
    """Dados extraídos de um comprovante via LLM Vision."""
    valor: Optional[float] = None
    estabelecimento: Optional[str] = None
    data: Optional[str] = None
    categoria_sugerida: Optional[str] = None
    tipo: Optional[str] = "EXPENSE"
    descricao: Optional[str] = None
    confianca: Optional[str] = "media"
