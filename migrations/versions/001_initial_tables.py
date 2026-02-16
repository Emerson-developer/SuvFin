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
    # === Users ===
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('phone', sa.String(20), unique=True, nullable=False, index=True),
        sa.Column('name', sa.String(100), nullable=True),
        sa.Column(
            'license_type',
            sa.Enum('FREE_TRIAL', 'BASICO', 'PRO', 'PREMIUM', name='licensetype'),
            nullable=False,
            server_default='FREE_TRIAL',
        ),
        sa.Column('license_expires_at', sa.Date(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('abacatepay_customer_id', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )

    # === Categories ===
    op.create_table(
        'categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('emoji', sa.String(10), nullable=True),
        sa.Column('color', sa.String(7), nullable=True),
        sa.Column('is_default', sa.Boolean(), server_default=sa.text('true')),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
    )

    # === Transactions ===
    op.create_table(
        'transactions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'type',
            sa.Enum('INCOME', 'EXPENSE', name='transactiontype'),
            nullable=False,
        ),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column(
            'category_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('categories.id'),
            nullable=True,
        ),
        sa.Column('receipt_url', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
    )

    # === Payments ===
    op.create_table(
        'payments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column(
            'abacatepay_billing_id',
            sa.String(100),
            unique=True,
            nullable=False,
            index=True,
        ),
        sa.Column('abacatepay_customer_id', sa.String(100), nullable=True),
        sa.Column('plan_type', sa.String(20), nullable=True, server_default='PRO'),
        sa.Column('billing_period', sa.String(20), nullable=True, server_default='MONTHLY'),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column(
            'status',
            sa.Enum(
                'PENDING', 'PAID', 'EXPIRED', 'CANCELLED', 'REFUNDED',
                name='paymentstatus',
            ),
            nullable=False,
            server_default='PENDING',
        ),
        sa.Column('payment_method', sa.String(20), server_default='PIX'),
        sa.Column('payment_url', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table('payments')
    op.drop_table('transactions')
    op.drop_table('categories')
    op.drop_table('users')
    op.execute('DROP TYPE IF EXISTS paymentstatus')
    op.execute('DROP TYPE IF EXISTS transactiontype')
    op.execute('DROP TYPE IF EXISTS licensetype')
