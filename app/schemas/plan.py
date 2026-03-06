"""
Schemas Pydantic para planos.
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class PlanOut(BaseModel):
    id: str
    name: str
    price: float
    features: List[str]
    billing_cycle: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
