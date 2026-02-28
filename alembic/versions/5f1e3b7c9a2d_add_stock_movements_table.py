"""Add stock_movements table

Revision ID: 5f1e3b7c9a2d
Revises: 3a2c4f5e6b8d
Create Date: 2026-02-28

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# ==========================================================
# Revision identifiers
# ==========================================================

revision: str = '5f1e3b7c9a2d'
down_revision: Union[str, Sequence[str], None] = '3a2c4f5e6b8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema.

    Best practices applied:
    - All constraints have explicit names.
    - Correct creation order according to dependencies.
    - Constraints declared explicitly to facilitate future drop/alter operations.
    - Enums stored as VARCHAR in MySQL for compatibility.
    """

    # ==========================================================
    # Table: stock_movements
    # Depends on items and branches
    # ==========================================================
    op.create_table(
        'stock_movements',

        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('quantity', sa.Numeric(10, 3), nullable=False),
        sa.Column(
            'movement_type',
            sa.String(length=20),
            nullable=False,
            comment='Enum: IN, OUT, TRANSFER, ADJUSTMENT'
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=False),

        sa.PrimaryKeyConstraint('id', name='pk_stock_movements'),

        # FK with explicit names
        sa.ForeignKeyConstraint(
            ['item_id'],
            ['items.id'],
            name='fk_stock_movements_item_id'
        ),
        sa.ForeignKeyConstraint(
            ['branch_id'],
            ['branches.id'],
            name='fk_stock_movements_branch_id'
        )
    )


def downgrade() -> None:
    """
    Downgrade schema.

    Important:
    - Drop stock_movements table.
    """

    op.drop_table('stock_movements')
