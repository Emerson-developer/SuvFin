"""
Serviço de transações financeiras (CRUD).
"""

from datetime import date, datetime
from uuid import UUID
from typing import Optional

from sqlalchemy import select, desc, func, or_
from sqlalchemy.orm import selectinload
from loguru import logger

from app.config.database import async_session
from app.models.transaction import Transaction, TransactionType
from app.models.category import Category
from app.services.finance.category_service import CategoryService


class TransactionService:
    """CRUD para transações financeiras."""

    def __init__(self):
        self.category_service = CategoryService()

    async def create(
        self,
        user_id: str,
        tx_type: TransactionType,
        amount: float,
        description: str = None,
        category_name: str = None,
        tx_date: date = None,
        receipt_url: str = None,
    ) -> dict:
        """Cria uma nova transação."""
        async with async_session() as session:
            # Resolver categoria
            category = None
            if category_name:
                category = await self.category_service.find_or_create(
                    session, category_name, user_id
                )

            transaction = Transaction(
                user_id=UUID(user_id),
                type=tx_type,
                amount=amount,
                description=description,
                date=tx_date or date.today(),
                category_id=category.id if category else None,
                receipt_url=receipt_url,
            )

            session.add(transaction)
            await session.commit()
            await session.refresh(transaction)

            logger.info(
                f"Transação criada: {transaction.id} | "
                f"{tx_type.value} R${amount} | user={user_id}"
            )

            return {
                "id": str(transaction.id),
                "type": tx_type.value,
                "amount": float(transaction.amount),
                "description": transaction.description,
                "date": transaction.date,
                "category_name": category.name if category else None,
                "category_emoji": category.emoji if category else "📦",
            }

    async def get_by_id(self, transaction_id: str, user_id: str) -> Optional[dict]:
        """Busca transação por ID."""
        async with async_session() as session:
            stmt = (
                select(Transaction)
                .options(selectinload(Transaction.category))
                .where(
                    Transaction.id == UUID(transaction_id),
                    Transaction.user_id == UUID(user_id),
                    Transaction.deleted_at.is_(None),
                )
            )
            result = await session.execute(stmt)
            tx = result.scalar_one_or_none()

            if not tx:
                return None

            return self._to_dict(tx)

    async def get_last(self, user_id: str) -> Optional[dict]:
        """Retorna o último lançamento do usuário."""
        async with async_session() as session:
            stmt = (
                select(Transaction)
                .options(selectinload(Transaction.category))
                .where(
                    Transaction.user_id == UUID(user_id),
                    Transaction.deleted_at.is_(None),
                )
                .order_by(desc(Transaction.created_at))
                .limit(1)
            )
            result = await session.execute(stmt)
            tx = result.scalar_one_or_none()

            return self._to_dict(tx) if tx else None

    async def get_recent(
        self,
        user_id: str,
        limit: int = 5,
        tx_type: str = None,
    ) -> list[dict]:
        """Retorna últimos N lançamentos."""
        async with async_session() as session:
            stmt = (
                select(Transaction)
                .options(selectinload(Transaction.category))
                .where(
                    Transaction.user_id == UUID(user_id),
                    Transaction.deleted_at.is_(None),
                )
            )

            if tx_type and tx_type in ("INCOME", "EXPENSE"):
                stmt = stmt.where(
                    Transaction.type == TransactionType(tx_type)
                )

            stmt = stmt.order_by(desc(Transaction.created_at)).limit(limit)

            result = await session.execute(stmt)
            transactions = result.scalars().all()

            return [self._to_dict(tx) for tx in transactions]

    async def search(
        self, user_id: str, query: str, limit: int = 5
    ) -> list[dict]:
        """Busca lançamentos por descrição (case-insensitive)."""
        async with async_session() as session:
            stmt = (
                select(Transaction)
                .options(selectinload(Transaction.category))
                .where(
                    Transaction.user_id == UUID(user_id),
                    Transaction.deleted_at.is_(None),
                    or_(
                        Transaction.description.ilike(f"%{query}%"),
                    ),
                )
                .order_by(desc(Transaction.created_at))
                .limit(limit)
            )
            result = await session.execute(stmt)
            transactions = result.scalars().all()

            return [self._to_dict(tx) for tx in transactions]

    async def soft_delete(self, transaction_id: str, user_id: str) -> bool:
        """Soft delete de uma transação."""
        async with async_session() as session:
            stmt = select(Transaction).where(
                Transaction.id == UUID(transaction_id),
                Transaction.user_id == UUID(user_id),
                Transaction.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            tx = result.scalar_one_or_none()

            if not tx:
                return False

            tx.deleted_at = datetime.utcnow()
            await session.commit()

            logger.info(f"Transação removida (soft): {transaction_id}")
            return True

    async def update(
        self, transaction_id: str, user_id: str, updates: dict
    ) -> bool:
        """Atualiza campos de uma transação."""
        async with async_session() as session:
            stmt = select(Transaction).where(
                Transaction.id == UUID(transaction_id),
                Transaction.user_id == UUID(user_id),
                Transaction.deleted_at.is_(None),
            )
            result = await session.execute(stmt)
            tx = result.scalar_one_or_none()

            if not tx:
                return False

            if "amount" in updates:
                tx.amount = updates["amount"]
            if "description" in updates:
                tx.description = updates["description"]
            if "date" in updates:
                tx.date = updates["date"]
            if "category_name" in updates:
                category = await self.category_service.find_or_create(
                    session, updates["category_name"], user_id
                )
                tx.category_id = category.id

            tx.updated_at = datetime.utcnow()
            await session.commit()

            logger.info(f"Transação atualizada: {transaction_id}")
            return True

    def _to_dict(self, tx: Transaction) -> dict:
        """Converte Transaction model para dict."""
        return {
            "id": str(tx.id),
            "type": tx.type.value if tx.type else None,
            "amount": float(tx.amount),
            "description": tx.description,
            "date": tx.date,
            "category_name": tx.category.name if tx.category else None,
            "category_emoji": tx.category.emoji if tx.category else "📦",
            "receipt_url": tx.receipt_url,
            "created_at": tx.created_at,
        }
