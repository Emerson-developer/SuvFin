"""Initial tables - users, categories, transactions, payments

Revision ID: 001_initial
Revises: 
Create Date: 2026-02-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Criar enums primeiro (só se não existirem)
    op.execute("DO $$ BEGIN CREATE TYPE licensetype AS ENUM ('FREE_TRIAL', 'PREMIUM'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE transactiontype AS ENUM ('INCOME', 'EXPENSE'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE paymentstatus AS ENUM ('PENDING', 'PAID', 'EXPIRED', 'CANCELLED', 'REFUNDED'); EXCEPTION WHEN duplicate_object THEN NULL; END $$;")

    # === Users ===
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY,
            phone VARCHAR(20) UNIQUE NOT NULL,
            name VARCHAR(100),
            license_type licensetype NOT NULL DEFAULT 'FREE_TRIAL',
            license_expires_at DATE,
            is_active BOOLEAN DEFAULT true,
            abacatepay_customer_id VARCHAR(100),
            created_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_users_phone ON users(phone)")

    # === Categories ===
    op.execute("""
        CREATE TABLE IF NOT EXISTS categories (
            id UUID PRIMARY KEY,
            name VARCHAR(50) NOT NULL,
            emoji VARCHAR(10),
            color VARCHAR(7),
            is_default BOOLEAN DEFAULT true,
            user_id UUID,
            created_at TIMESTAMP
        )
    """)

    # === Transactions ===
    op.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id),
            type transactiontype NOT NULL,
            amount NUMERIC(12, 2) NOT NULL,
            description VARCHAR(255),
            date DATE NOT NULL,
            category_id UUID REFERENCES categories(id),
            receipt_url TEXT,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            deleted_at TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_transactions_user_id ON transactions(user_id)")

    # === Payments ===
    op.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            abacatepay_billing_id VARCHAR(100) UNIQUE NOT NULL,
            abacatepay_customer_id VARCHAR(100),
            amount_cents INTEGER NOT NULL,
            status paymentstatus NOT NULL DEFAULT 'PENDING',
            payment_method VARCHAR(20) DEFAULT 'PIX',
            payment_url TEXT,
            created_at TIMESTAMP,
            paid_at TIMESTAMP,
            updated_at TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_user_id ON payments(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_payments_abacatepay_billing_id ON payments(abacatepay_billing_id)")


def downgrade() -> None:
    op.execute('DROP TABLE IF EXISTS payments')
    op.execute('DROP TABLE IF EXISTS transactions')
    op.execute('DROP TABLE IF EXISTS categories')
    op.execute('DROP TABLE IF EXISTS users')
    op.execute('DROP TYPE IF EXISTS paymentstatus')
    op.execute('DROP TYPE IF EXISTS transactiontype')
    op.execute('DROP TYPE IF EXISTS licensetype')
