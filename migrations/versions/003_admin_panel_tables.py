"""Add admin panel tables: plans, subscriptions, conversations, messages, admin_users.
Extend users with email, avatar_url, notes.

Revision ID: 003_admin_panel
Revises: 002_add_plans
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '003_admin_panel'
down_revision: Union[str, None] = '002_add_plans'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # =========================================================
    # 1. Estender tabela users com colunas do admin (contacts)
    # =========================================================
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN email TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN avatar_url TEXT;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE users ADD COLUMN notes TEXT DEFAULT '';
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """)

    # Trigger para atualizar updated_at automaticamente
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $func$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $func$ LANGUAGE plpgsql;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TRIGGER users_updated_at
                BEFORE UPDATE ON users
                FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # =========================================================
    # 2. Tabela plans
    # =========================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            price NUMERIC(10, 2) NOT NULL DEFAULT 0,
            features JSONB NOT NULL DEFAULT '[]'::jsonb,
            billing_cycle TEXT NOT NULL CHECK (billing_cycle IN ('free', 'monthly', 'yearly')),
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    # =========================================================
    # 3. Tabela subscriptions
    # =========================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS subscriptions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            plan_id UUID NOT NULL REFERENCES plans(id),
            status TEXT NOT NULL CHECK (status IN ('active', 'canceled', 'past_due', 'trial')),
            started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ,
            canceled_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (user_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id)")

    # =========================================================
    # 4. Tabela conversations
    # =========================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK (status IN ('open', 'closed')) DEFAULT 'open',
            last_message_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (user_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_conversations_last_message_at ON conversations(last_message_at DESC)")

    # =========================================================
    # 5. Tabela messages
    # =========================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            sender_type TEXT NOT NULL CHECK (sender_type IN ('admin', 'user')),
            content TEXT NOT NULL,
            message_type TEXT NOT NULL CHECK (message_type IN ('text', 'image', 'audio')) DEFAULT 'text',
            status TEXT NOT NULL CHECK (status IN ('sent', 'delivered', 'read')) DEFAULT 'sent',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at DESC)")

    # Trigger: atualizar conversations.last_message_at ao inserir mensagem
    op.execute("""
        CREATE OR REPLACE FUNCTION update_conversation_last_message()
        RETURNS TRIGGER AS $func$
        BEGIN
            UPDATE conversations
            SET last_message_at = NEW.created_at
            WHERE id = NEW.conversation_id;
            RETURN NEW;
        END;
        $func$ LANGUAGE plpgsql;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TRIGGER messages_update_last_message_at
                AFTER INSERT ON messages
                FOR EACH ROW EXECUTE FUNCTION update_conversation_last_message();
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # =========================================================
    # 6. Tabela admin_users (autenticação do painel)
    # =========================================================
    op.execute("""
        CREATE TABLE IF NOT EXISTS admin_users (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            username VARCHAR(50) UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TRIGGER admin_users_updated_at
                BEFORE UPDATE ON admin_users
                FOR EACH ROW EXECUTE FUNCTION update_updated_at();
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # =========================================================
    # 7. Seed: 3 planos padrão
    # =========================================================
    op.execute("""
        INSERT INTO plans (id, name, price, features, billing_cycle, is_active)
        VALUES
        (
            'a0000000-0000-0000-0000-000000000001',
            'Gratuito', 0,
            '["Controle de gastos basico","Relatorios mensais","1 conta bancaria","Suporte por email","Categorias padrao"]'::jsonb,
            'free', true
        ),
        (
            'a0000000-0000-0000-0000-000000000002',
            'Mensal', 19.90,
            '["Controle de gastos completo","IA para analise de gastos","Contas ilimitadas","Relatorios diarios","Categorias personalizadas","Metas financeiras","Exportacao PDF/Excel","Suporte por WhatsApp","Alertas de gastos"]'::jsonb,
            'monthly', true
        ),
        (
            'a0000000-0000-0000-0000-000000000003',
            'Anual', 190.00,
            '["Tudo do Mensal","IA para analise de gastos","Contas ilimitadas","Relatorios diarios","Metas financeiras","Exportacao PDF/Excel","Suporte prioritario","Economia de 25%"]'::jsonb,
            'yearly', true
        )
        ON CONFLICT DO NOTHING
    """)

    # =========================================================
    # 8. Migrar dados: criar subscriptions para users existentes
    # =========================================================
    # Users com FREE_TRIAL → subscription status='trial' no plano Gratuito
    op.execute("""
        INSERT INTO subscriptions (user_id, plan_id, status, started_at, expires_at)
        SELECT
            u.id,
            'a0000000-0000-0000-0000-000000000001'::uuid,
            'trial',
            COALESCE(u.created_at, now()),
            u.license_expires_at
        FROM users u
        WHERE u.license_type = 'FREE_TRIAL'
          AND NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.user_id = u.id)
    """)

    # Users com PRO + MONTHLY → subscription status='active' no plano Mensal
    # Detectar período via payments se disponível
    op.execute("""
        INSERT INTO subscriptions (user_id, plan_id, status, started_at, expires_at)
        SELECT
            u.id,
            CASE
                WHEN EXISTS (
                    SELECT 1 FROM payments p
                    WHERE p.user_id = u.id
                      AND p.status = 'PAID'
                      AND p.billing_period = 'ANNUAL'
                    ORDER BY p.paid_at DESC LIMIT 1
                ) THEN 'a0000000-0000-0000-0000-000000000003'::uuid
                ELSE 'a0000000-0000-0000-0000-000000000002'::uuid
            END,
            'active',
            COALESCE(u.created_at, now()),
            u.license_expires_at
        FROM users u
        WHERE u.license_type IN ('PRO', 'PREMIUM', 'BASICO')
          AND u.is_active = true
          AND NOT EXISTS (SELECT 1 FROM subscriptions s WHERE s.user_id = u.id)
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS messages_update_last_message_at ON messages")
    op.execute("DROP FUNCTION IF EXISTS update_conversation_last_message()")
    op.execute("DROP TRIGGER IF EXISTS admin_users_updated_at ON admin_users")
    op.execute("DROP TABLE IF EXISTS admin_users")
    op.execute("DROP TABLE IF EXISTS messages")
    op.execute("DROP TABLE IF EXISTS conversations")
    op.execute("DROP TABLE IF EXISTS subscriptions")
    op.execute("DROP TABLE IF EXISTS plans")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS email")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS avatar_url")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS notes")
    op.execute("DROP TRIGGER IF EXISTS users_updated_at ON users")
    # Keep update_updated_at function as it may be used elsewhere
