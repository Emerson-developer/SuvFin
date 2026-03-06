"""
Auth middleware: dependency FastAPI para proteger rotas admin com JWT.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config.settings import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Bearer token scheme
security = HTTPBearer()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica senha contra o hash bcrypt."""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Gera hash bcrypt da senha."""
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Cria JWT token para admin."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ADMIN_JWT_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.ADMIN_JWT_SECRET_KEY,
        algorithm=settings.ADMIN_JWT_ALGORITHM,
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decodifica e valida JWT token."""
    return jwt.decode(
        token,
        settings.ADMIN_JWT_SECRET_KEY,
        algorithms=[settings.ADMIN_JWT_ALGORITHM],
    )


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    FastAPI dependency — valida o JWT e retorna os dados do admin.
    Use como: Depends(get_current_admin)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(credentials.credentials)
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        return {"username": username, "admin_id": payload.get("admin_id")}
    except JWTError:
        raise credentials_exception
