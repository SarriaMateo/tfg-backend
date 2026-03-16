"""Add square meter to item unit schema comment

Revision ID: a1b2c3d4e5f6
Revises: 8d4f1e7c3a5b
Create Date: 2026-03-16

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '8d4f1e7c3a5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Keep the items.unit schema metadata aligned with the application enum."""
    op.alter_column(
        'items',
        'unit',
        existing_type=sa.String(length=10),
        existing_nullable=False,
        comment='Enum: ud, kg, g, l, ml, m, m2, box, pack'
    )


def downgrade() -> None:
    """Restore the previous items.unit schema comment."""
    op.alter_column(
        'items',
        'unit',
        existing_type=sa.String(length=10),
        existing_nullable=False,
        comment='Enum: ud, kg, g, l, ml, m, box, pack'
    )
