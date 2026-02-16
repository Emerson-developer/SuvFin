"""Add plan types (BASICO, PRO) and payment plan columns

Revision ID: 002_add_plans
Revises: 001_initial
Create Date: 2026-02-16

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '002_add_plans'
down_revision: Union[str, None] = '001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Adicionar novos valores ao enum licensetype (idempotente)
    op.execute("""
        DO $$ BEGIN
            ALTER TYPE licensetype ADD VALUE IF NOT EXISTS 'BASICO';
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TYPE licensetype ADD VALUE IF NOT EXISTS 'PRO';
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # Adicionar colunas à tabela payments (idempotente)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE payments ADD COLUMN plan_type VARCHAR(20) DEFAULT 'PRO';
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE payments ADD COLUMN billing_period VARCHAR(20) DEFAULT 'MONTHLY';
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS billing_period")
    op.execute("ALTER TABLE payments DROP COLUMN IF EXISTS plan_type")
    # Nota: PostgreSQL não permite remover valores de enum facilmente
