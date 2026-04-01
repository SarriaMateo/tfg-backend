"""Add low_stock_threshold field to items

Revision ID: e2b7c1d9f4a6
Revises: c4f9a1e2b7d3
Create Date: 2026-04-02

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e2b7c1d9f4a6'
down_revision: Union[str, Sequence[str], None] = 'c4f9a1e2b7d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add items.low_stock_threshold with a safe backfill default for existing rows."""
    op.add_column(
        'items',
        sa.Column('low_stock_threshold', sa.Integer(), nullable=False, server_default='0')
    )
    op.alter_column('items', 'low_stock_threshold', server_default=None)


def downgrade() -> None:
    """Remove items.low_stock_threshold."""
    op.drop_column('items', 'low_stock_threshold')
