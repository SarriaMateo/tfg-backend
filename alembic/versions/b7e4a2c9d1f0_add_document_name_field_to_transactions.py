"""Add document_name field to transactions

Revision ID: b7e4a2c9d1f0
Revises: 6e2a1b9c4d7f
Create Date: 2026-03-27

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7e4a2c9d1f0'
down_revision: Union[str, Sequence[str], None] = '6e2a1b9c4d7f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add transactions.document_name to store the original document filename."""
    op.add_column('transactions', sa.Column('document_name', sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Remove transactions.document_name."""
    op.drop_column('transactions', 'document_name')
