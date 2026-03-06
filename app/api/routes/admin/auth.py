"""
Rotas de autenticação admin.
POST /api/v1/admin/auth/login
"""

from fastapi import APIRouter, HTTPException, status

from app.schemas.admin import AdminLogin, TokenResponse
from app.services.admin.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["admin-auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: AdminLogin):
    """
    Autentica um admin e retorna JWT token.
    """
    auth_service = AuthService()
    result = await auth_service.authenticate(body.username, body.password)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return result
