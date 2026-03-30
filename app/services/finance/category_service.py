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

    async def create_custom(
        self,
        session: AsyncSession,
        user_id: str,
        name: str,
        emoji: Optional[str] = None,
    ) -> Category:
        """Cria uma categoria personalizada para o usuário.

        Raises:
            ValueError: Se já existe uma categoria com esse nome (padrão ou do usuário).
        """
        # Verificar duplicata
        stmt = select(Category).where(
            Category.name.ilike(name),
            or_(
                Category.user_id.is_(None),
                Category.user_id == UUID(user_id),
            ),
        )
        result = await session.execute(stmt)
        if result.scalar_one_or_none():
            raise ValueError(f"Já existe uma categoria com o nome '{name}'.")

        category = Category(
            name=name.title(),
            emoji=emoji or "📦",
            is_default=False,
            user_id=UUID(user_id),
        )
        session.add(category)
        await session.flush()
        return category

    async def delete_custom(
        self,
        session: AsyncSession,
        user_id: str,
        name: str,
    ) -> bool:
        """Remove uma categoria personalizada do usuário.

        Returns:
            True se removida, False se não encontrada.
        Raises:
            ValueError: Se a categoria for padrão (não pode ser removida).
        """
        # Checar se existe como padrão
        default_stmt = select(Category).where(
            Category.name.ilike(name),
            Category.user_id.is_(None),
        )
        result = await session.execute(default_stmt)
        if result.scalar_one_or_none():
            raise ValueError("Categorias padrão não podem ser removidas.")

        # Buscar categoria custom do usuário
        custom_stmt = select(Category).where(
            Category.name.ilike(name),
            Category.user_id == UUID(user_id),
            Category.is_default.is_(False),
        )
        result = await session.execute(custom_stmt)
        category = result.scalar_one_or_none()

        if not category:
            return False

        await session.delete(category)
        return True

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
