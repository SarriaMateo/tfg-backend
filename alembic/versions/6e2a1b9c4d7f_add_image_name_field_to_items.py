"""Add image_name field to items

Revision ID: 6e2a1b9c4d7f
Revises: a1b2c3d4e5f6
Create Date: 2026-03-26

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6e2a1b9c4d7f'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add items.image_name to store the original image filename."""
    op.add_column('items', sa.Column('image_name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Remove items.image_name."""
    op.drop_column('items', 'image_name')
