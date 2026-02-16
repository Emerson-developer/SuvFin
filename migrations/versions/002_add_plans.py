"""Add plan types (BASICO, PRO) and payment plan columns

Revision ID: 002_add_plans
Revises: 001_initial
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_add_plans'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ADD VALUE não pode rodar dentro de uma transação no PostgreSQL.
    # Então fazemos commit da transação atual, adicionamos os valores,
    # e depois continuamos com as alterações de tabela normalmente.
    op.execute("COMMIT")
    op.execute("ALTER TYPE licensetype ADD VALUE IF NOT EXISTS 'BASICO'")
    op.execute("ALTER TYPE licensetype ADD VALUE IF NOT EXISTS 'PRO'")
    op.execute("BEGIN")

    # Add plan_type and billing_period columns to payments table
    op.add_column(
        'payments',
        sa.Column('plan_type', sa.String(20), nullable=True, server_default='PRO'),
    )
    op.add_column(
        'payments',
        sa.Column('billing_period', sa.String(20), nullable=True, server_default='MONTHLY'),
    )


def downgrade() -> None:
    op.drop_column('payments', 'billing_period')
    op.drop_column('payments', 'plan_type')
    # Note: PostgreSQL does not support removing enum values easily
