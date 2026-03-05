"""Rename metadata column to event_metadata in transaction_events

Revision ID: 8d4f1e7c3a5b
Revises: 7c3e8f9d2a4b
Create Date: 2026-03-05

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# ==========================================================
# Revision identifiers
# ==========================================================

revision: str = '8d4f1e7c3a5b'
down_revision: Union[str, Sequence[str], None] = '7c3e8f9d2a4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema.

    Changes:
    - Rename 'metadata' column to 'event_metadata' in transaction_events table
      (metadata is a reserved attribute name in SQLAlchemy's Declarative API)
    """

    # ==========================================================
    # Table: transaction_events
    # Rename reserved column name
    # ==========================================================
    op.alter_column(
        'transaction_events',
        'metadata',
        new_column_name='event_metadata',
        existing_type=sa.JSON(),
        existing_nullable=True
    )


def downgrade() -> None:
    """
    Downgrade schema.

    Changes:
    - Rename 'event_metadata' column back to 'metadata' in transaction_events table
    """

    # ==========================================================
    # Table: transaction_events
    # Revert column name change
    # ==========================================================
    op.alter_column(
        'transaction_events',
        'event_metadata',
        new_column_name='metadata',
        existing_type=sa.JSON(),
        existing_nullable=True
    )
