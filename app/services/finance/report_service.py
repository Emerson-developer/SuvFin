"""
Serviço de relatórios financeiros.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID
from typing import Optional

from sqlalchemy import select, func, desc, case
from sqlalchemy.orm import selectinload

from app.config.database import async_session
from app.models.transaction import Transaction, TransactionType
from app.models.category import Category


class ReportService:
    """Gera relatórios financeiros."""

    async def generate_period_report(
        self,
        user_id: str,
        start_date: date,
        end_date: date,
    ) -> dict:
        """Relatório financeiro por período."""
        async with async_session() as session:
            uid = UUID(user_id)

            # Totais por tipo
            totals_stmt = select(
                Transaction.type,
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("count"),
            ).where(
                Transaction.user_id == uid,
                Transaction.deleted_at.is_(None),
                Transaction.date >= start_date,
                Transaction.date <= end_date,
            ).group_by(Transaction.type)

            result = await session.execute(totals_stmt)
            rows = result.all()

            total_income = 0.0
            total_expense = 0.0
            tx_count = 0

            for row in rows:
                amount = float(row.total) if row.total else 0.0
                count = row.count or 0
                if row.type == TransactionType.INCOME:
                    total_income = amount
                else:
                    total_expense = amount
                tx_count += count

            # Por categoria (apenas expenses)
            cat_stmt = (
                select(
                    Category.name,
                    Category.emoji,
                    func.sum(Transaction.amount).label("total"),
                    func.count(Transaction.id).label("count"),
                )
                .join(Category, Transaction.category_id == Category.id, isouter=True)
                .where(
                    Transaction.user_id == uid,
                    Transaction.deleted_at.is_(None),
                    Transaction.type == TransactionType.EXPENSE,
                    Transaction.date >= start_date,
                    Transaction.date <= end_date,
                )
                .group_by(Category.name, Category.emoji)
                .order_by(desc(func.sum(Transaction.amount)))
            )

            cat_result = await session.execute(cat_stmt)
            by_category = [
                {
                    "name": row.name or "Sem categoria",
                    "emoji": row.emoji or "📦",
                    "total": float(row.total),
                    "count": row.count,
                }
                for row in cat_result.all()
            ]

            return {
                "total_income": total_income,
                "total_expense": total_expense,
                "balance": total_income - total_expense,
                "transaction_count": tx_count,
                "by_category": by_category,
            }

    async def generate_category_report(
        self,
        user_id: str,
        start_date: date,
        end_date: date,
        category_filter: str = None,
    ) -> list[dict]:
        """Relatório agrupado por categoria."""
        async with async_session() as session:
            uid = UUID(user_id)

            stmt = (
                select(
                    Category.name,
                    Category.emoji,
                    func.sum(Transaction.amount).label("total"),
                    func.count(Transaction.id).label("count"),
                    func.avg(Transaction.amount).label("average"),
                )
                .join(Category, Transaction.category_id == Category.id, isouter=True)
                .where(
                    Transaction.user_id == uid,
                    Transaction.deleted_at.is_(None),
                    Transaction.type == TransactionType.EXPENSE,
                    Transaction.date >= start_date,
                    Transaction.date <= end_date,
                )
            )

            if category_filter:
                stmt = stmt.where(Category.name.ilike(f"%{category_filter}%"))

            stmt = stmt.group_by(Category.name, Category.emoji).order_by(
                desc(func.sum(Transaction.amount))
            )

            result = await session.execute(stmt)
            rows = result.all()

            # Calcular total geral para percentuais
            grand_total = sum(float(r.total) for r in rows) if rows else 1

            categories = []
            for row in rows:
                total = float(row.total)
                categories.append({
                    "name": row.name or "Sem categoria",
                    "emoji": row.emoji or "📦",
                    "total": total,
                    "count": row.count,
                    "average": float(row.average) if row.average else 0.0,
                    "percentage": (total / grand_total) * 100,
                })

            # Se filtro de categoria, buscar últimas transações
            if category_filter and categories:
                tx_stmt = (
                    select(Transaction)
                    .join(Category, Transaction.category_id == Category.id)
                    .where(
                        Transaction.user_id == uid,
                        Transaction.deleted_at.is_(None),
                        Category.name.ilike(f"%{category_filter}%"),
                        Transaction.date >= start_date,
                        Transaction.date <= end_date,
                    )
                    .order_by(desc(Transaction.date))
                    .limit(5)
                )
                tx_result = await session.execute(tx_stmt)
                txs = tx_result.scalars().all()

                categories[0]["transactions"] = [
                    {
                        "description": tx.description,
                        "amount": float(tx.amount),
                        "date": tx.date,
                    }
                    for tx in txs
                ]

            return categories

    async def get_balance(self, user_id: str) -> dict:
        """Retorna o saldo geral (entradas - saídas)."""
        async with async_session() as session:
            uid = UUID(user_id)

            stmt = select(
                Transaction.type,
                func.sum(Transaction.amount).label("total"),
            ).where(
                Transaction.user_id == uid,
                Transaction.deleted_at.is_(None),
            ).group_by(Transaction.type)

            result = await session.execute(stmt)
            rows = result.all()

            total_income = 0.0
            total_expense = 0.0

            for row in rows:
                if row.type == TransactionType.INCOME:
                    total_income = float(row.total) if row.total else 0.0
                else:
                    total_expense = float(row.total) if row.total else 0.0

            return {
                "total_income": total_income,
                "total_expense": total_expense,
                "balance": total_income - total_expense,
            }
