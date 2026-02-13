"""
Serviço de categorias.
"""

from uuid import UUID
from typing import Optional

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.database import async_session
from app.models.category import Category, DEFAULT_CATEGORIES


class CategoryService:
    """Gerencia categorias de transações."""

    async def find_or_create(
        self,
        session: AsyncSession,
        name: str,
        user_id: str,
    ) -> Category:
        """Busca categoria por nome (case-insensitive) ou cria uma nova."""
        # Buscar nas categorias padrão e do usuário
        stmt = select(Category).where(
            Category.name.ilike(name),
            or_(
                Category.user_id.is_(None),  # Padrão
                Category.user_id == UUID(user_id),  # Custom do usuário
            ),
        )
        result = await session.execute(stmt)
        category = result.scalar_one_or_none()

        if category:
            return category

        # Tentar encontrar emoji padrão
        emoji = "📦"
        for default_cat in DEFAULT_CATEGORIES:
            if default_cat["name"].lower() == name.lower():
                emoji = default_cat["emoji"]
                break

        # Criar nova categoria custom
        category = Category(
            name=name.title(),
            emoji=emoji,
            is_default=False,
            user_id=UUID(user_id),
        )
        session.add(category)
        await session.flush()

        return category

    async def get_all(self, user_id: str) -> list[dict]:
        """Retorna todas as categorias (padrão + custom do usuário)."""
        async with async_session() as session:
            stmt = (
                select(Category)
                .where(
                    or_(
                        Category.user_id.is_(None),
                        Category.user_id == UUID(user_id),
                    )
                )
                .order_by(Category.name)
            )
            result = await session.execute(stmt)
            categories = result.scalars().all()

            return [
                {
                    "id": str(cat.id),
                    "name": cat.name,
                    "emoji": cat.emoji or "📦",
                    "is_default": cat.is_default,
                }
                for cat in categories
            ]

    async def seed_defaults(self):
        """Cria as categorias padrão no banco (rodar 1x no setup)."""
        async with async_session() as session:
            for cat_data in DEFAULT_CATEGORIES:
                exists_stmt = select(Category).where(
                    Category.name == cat_data["name"],
                    Category.is_default.is_(True),
                )
                result = await session.execute(exists_stmt)
                if not result.scalar_one_or_none():
                    category = Category(
                        name=cat_data["name"],
                        emoji=cat_data["emoji"],
                        color=cat_data["color"],
                        is_default=True,
                        user_id=None,
                    )
                    session.add(category)

            await session.commit()
