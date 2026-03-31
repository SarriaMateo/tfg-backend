"""Add last_event_at field to transactions

Revision ID: c4f9a1e2b7d3
Revises: b7e4a2c9d1f0
Create Date: 2026-03-31

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4f9a1e2b7d3'
down_revision: Union[str, Sequence[str], None] = 'b7e4a2c9d1f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add transactions.last_event_at to track the timestamp of the latest event."""
    op.add_column('transactions', sa.Column('last_event_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Remove transactions.last_event_at."""
    op.drop_column('transactions', 'last_event_at')
