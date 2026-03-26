"""Add Pluggy Open Finance tables: pluggy_connection_configs, pluggy_items, pluggy_accounts, pluggy_transactions.

Revision ID: 004_pluggy_openfinance
Revises: 003_admin_panel
Create Date: 2026-03-25

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '004_pluggy_openfinance'
down_revision: Union[str, None] = '003_admin_panel'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================
    # 1. Tabela pluggy_connection_configs
    # =========================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS pluggy_connection_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            max_connections INTEGER NOT NULL DEFAULT 2,
            active_connections INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (user_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_pluggy_conn_config_user ON pluggy_connection_configs(user_id)")

    op.execute("""
        DO $$ BEGIN
            CREATE TRIGGER pluggy_connection_configs_updated_at
                BEFORE UPDATE ON pluggy_connection_configs
                FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # =========================================================
    # 2. Tabela pluggy_items
    # =========================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS pluggy_items (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            pluggy_item_id VARCHAR(100) NOT NULL UNIQUE,
            connector_name VARCHAR(200),
            connector_id INTEGER,
            status VARCHAR(50) NOT NULL DEFAULT 'UPDATING',
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_sync_at TIMESTAMPTZ,
            consent_expires_at TIMESTAMPTZ,
            connected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            disconnected_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_pluggy_items_user ON pluggy_items(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pluggy_items_pluggy_id ON pluggy_items(pluggy_item_id)")

    op.execute("""
        DO $$ BEGIN
            CREATE TRIGGER pluggy_items_updated_at
                BEFORE UPDATE ON pluggy_items
                FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # =========================================================
    # 3. Tabela pluggy_accounts
    # =========================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS pluggy_accounts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            pluggy_item_id UUID NOT NULL REFERENCES pluggy_items(id) ON DELETE CASCADE,
            pluggy_account_id VARCHAR(100) NOT NULL UNIQUE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name VARCHAR(200),
            type VARCHAR(50) NOT NULL DEFAULT 'BANK',
            subtype VARCHAR(50),
            number VARCHAR(50),
            balance NUMERIC(12, 2),
            currency_code VARCHAR(10) DEFAULT 'BRL',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_pluggy_accounts_item ON pluggy_accounts(pluggy_item_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pluggy_accounts_user ON pluggy_accounts(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pluggy_accounts_pluggy_id ON pluggy_accounts(pluggy_account_id)")

    op.execute("""
        DO $$ BEGIN
            CREATE TRIGGER pluggy_accounts_updated_at
                BEFORE UPDATE ON pluggy_accounts
                FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # =========================================================
    # 4. Tabela pluggy_transactions
    # =========================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS pluggy_transactions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            pluggy_account_id UUID NOT NULL REFERENCES pluggy_accounts(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            pluggy_transaction_id VARCHAR(100) NOT NULL UNIQUE,
            description VARCHAR(500),
            description_raw VARCHAR(500),
            amount NUMERIC(12, 2) NOT NULL,
            date DATE NOT NULL DEFAULT CURRENT_DATE,
            type VARCHAR(20) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'POSTED',
            category VARCHAR(200),
            category_id UUID REFERENCES categories(id),
            payment_method VARCHAR(50),
            currency_code VARCHAR(10) DEFAULT 'BRL',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_pluggy_tx_account ON pluggy_transactions(pluggy_account_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pluggy_tx_user ON pluggy_transactions(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pluggy_tx_pluggy_id ON pluggy_transactions(pluggy_transaction_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_pluggy_tx_user_date ON pluggy_transactions(user_id, date)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS pluggy_transactions CASCADE")
    op.execute("DROP TABLE IF EXISTS pluggy_accounts CASCADE")
    op.execute("DROP TABLE IF EXISTS pluggy_items CASCADE")
    op.execute("DROP TABLE IF EXISTS pluggy_connection_configs CASCADE")
