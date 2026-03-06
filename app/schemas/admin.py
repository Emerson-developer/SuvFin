"""
Schemas Pydantic para autenticação admin.
"""

from pydantic import BaseModel


class AdminLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
