"""Add profile (PF/PJ) field to users, transactions, pluggy_accounts, pluggy_transactions.

Revision ID: 005_add_profile_field
Revises: 004_pluggy_openfinance
Create Date: 2026-03-29

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '005_add_profile_field'
down_revision: Union[str, None] = '004_pluggy_openfinance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================
    # 1. Enum type (reuse across tables)
    # =========================================================
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE profile_type AS ENUM ('PF', 'PJ');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # =========================================================
    # 2. users — default_profile
    # =========================================================
    op.execute("""
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS default_profile profile_type NOT NULL DEFAULT 'PF'
    """)

    # =========================================================
    # 3. transactions — profile
    # =========================================================
    op.execute("""
        ALTER TABLE transactions
            ADD COLUMN IF NOT EXISTS profile profile_type NOT NULL DEFAULT 'PF'
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_transactions_profile ON transactions(user_id, profile)"
    )

    # =========================================================
    # 4. pluggy_accounts — profile
    # =========================================================
    op.execute("""
        ALTER TABLE pluggy_accounts
            ADD COLUMN IF NOT EXISTS profile profile_type NOT NULL DEFAULT 'PF'
    """)

    # =========================================================
    # 5. pluggy_transactions — profile
    # =========================================================
    op.execute("""
        ALTER TABLE pluggy_transactions
            ADD COLUMN IF NOT EXISTS profile profile_type NOT NULL DEFAULT 'PF'
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_pluggy_tx_profile ON pluggy_transactions(user_id, profile)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_pluggy_tx_profile")
    op.execute("ALTER TABLE pluggy_transactions DROP COLUMN IF EXISTS profile")

    op.execute("ALTER TABLE pluggy_accounts DROP COLUMN IF EXISTS profile")

    op.execute("DROP INDEX IF EXISTS idx_transactions_profile")
    op.execute("ALTER TABLE transactions DROP COLUMN IF EXISTS profile")

    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS default_profile")

    op.execute("DROP TYPE IF EXISTS profile_type")
