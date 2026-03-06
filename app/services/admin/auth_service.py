"""
Serviço de autenticação admin — login, criação de admin, JWT.
"""

from typing import Optional

from sqlalchemy import select
from loguru import logger

from app.config.database import async_session
from app.models.admin_user import AdminUser
from app.api.middleware.auth import verify_password, hash_password, create_access_token


class AuthService:
    """Gerencia autenticação de administradores."""

    async def authenticate(self, username: str, password: str) -> Optional[dict]:
        """
        Autentica admin e retorna token JWT.
        Retorna None se credenciais inválidas.
        """
        async with async_session() as session:
            stmt = select(AdminUser).where(
                AdminUser.username == username,
                AdminUser.is_active.is_(True),
            )
            result = await session.execute(stmt)
            admin = result.scalar_one_or_none()

            if not admin or not verify_password(password, admin.password_hash):
                logger.warning(f"Login falhou para username: {username}")
                return None

            token = create_access_token(
                data={"sub": admin.username, "admin_id": str(admin.id)}
            )
            logger.info(f"Admin autenticado: {username}")
            return {"access_token": token, "token_type": "bearer"}

    async def create_admin(self, username: str, password: str) -> AdminUser:
        """Cria um novo admin (para seed/setup)."""
        async with async_session() as session:
            admin = AdminUser(
                username=username,
                password_hash=hash_password(password),
            )
            session.add(admin)
            await session.commit()
            await session.refresh(admin)
            logger.info(f"Admin criado: {username}")
            return admin

    async def get_admin_by_username(self, username: str) -> Optional[AdminUser]:
        """Busca admin por username."""
        async with async_session() as session:
            stmt = select(AdminUser).where(AdminUser.username == username)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
