"""Add transaction tables and modify stock_movements

Revision ID: 7c3e8f9d2a4b
Revises: 4b5c6d7e8f9a
Create Date: 2026-03-04

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# ==========================================================
# Revision identifiers
# ==========================================================

revision: str = '7c3e8f9d2a4b'
down_revision: Union[str, Sequence[str], None] = '4b5c6d7e8f9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema.

    Best practices applied:
    - All constraints have explicit names.
    - Correct creation order according to dependencies.
    - Constraints declared explicitly to facilitate future drop/alter operations.
    - Enums stored as VARCHAR in the database for flexibility.
    """

    # ==========================================================
    # Table: transactions
    # Depends on branches
    # ==========================================================
    op.create_table(
        'transactions',

        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            'operation_type',
            sa.String(length=20),
            nullable=False,
            comment='Enum: IN, OUT, TRANSFER, ADJUSTMENT'
        ),
        sa.Column(
            'status',
            sa.String(length=20),
            nullable=False,
            server_default='PENDING',
            comment='Enum: PENDING, CANCELLED, COMPLETED'
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('document_url', sa.String(length=255), nullable=True),
        sa.Column('branch_id', sa.Integer(), nullable=False),
        sa.Column('destination_branch_id', sa.Integer(), nullable=True),

        sa.PrimaryKeyConstraint('id', name='pk_transactions'),

        # FK with explicit names
        sa.ForeignKeyConstraint(
            ['branch_id'],
            ['branches.id'],
            name='fk_transactions_branch_id'
        ),
        sa.ForeignKeyConstraint(
            ['destination_branch_id'],
            ['branches.id'],
            name='fk_transactions_destination_branch_id'
        )
    )

    # ==========================================================
    # Table: transaction_lines
    # Depends on transactions and items
    # ==========================================================
    op.create_table(
        'transaction_lines',

        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('quantity', sa.Numeric(10, 3), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('transaction_id', sa.Integer(), nullable=False),

        sa.PrimaryKeyConstraint('id', name='pk_transaction_lines'),

        # FK with explicit names
        sa.ForeignKeyConstraint(
            ['item_id'],
            ['items.id'],
            name='fk_transaction_lines_item_id'
        ),
        sa.ForeignKeyConstraint(
            ['transaction_id'],
            ['transactions.id'],
            name='fk_transaction_lines_transaction_id'
        )
    )

    # ==========================================================
    # Table: transaction_events
    # Depends on transactions and users
    # ==========================================================
    op.create_table(
        'transaction_events',

        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column(
            'action_type',
            sa.String(length=20),
            nullable=False,
            comment='Enum: CREATED, EDITED, CANCELLED, COMPLETED'
        ),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('performed_by', sa.Integer(), nullable=False),

        sa.PrimaryKeyConstraint('id', name='pk_transaction_events'),

        # FK with explicit names
        sa.ForeignKeyConstraint(
            ['transaction_id'],
            ['transactions.id'],
            name='fk_transaction_events_transaction_id'
        ),
        sa.ForeignKeyConstraint(
            ['performed_by'],
            ['users.id'],
            name='fk_transaction_events_performed_by'
        )
    )

    # ==========================================================
    # Modify: stock_movements
    # Add transaction_id foreign key
    # ==========================================================
    op.add_column(
        'stock_movements',
        sa.Column('transaction_id', sa.Integer(), nullable=False)
    )

    op.create_foreign_key(
        'fk_stock_movements_transaction_id',
        'stock_movements',
        'transactions',
        ['transaction_id'],
        ['id']
    )


def downgrade() -> None:
    """
    Downgrade schema.

    Important:
    - Drop all new tables and revert modifications.
    """

    # Drop FK first, then column
    op.drop_constraint(
        'fk_stock_movements_transaction_id',
        'stock_movements',
        type_='foreignkey'
    )
    op.drop_column('stock_movements', 'transaction_id')

    # Drop tables in reverse order of creation (dependencies first)
    op.drop_table('transaction_events')
    op.drop_table('transaction_lines')
    op.drop_table('transactions')
