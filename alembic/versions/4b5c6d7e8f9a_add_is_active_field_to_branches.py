"""Add is_active field to branches table

Revision ID: 4b5c6d7e8f9a
Revises: 3a2c4f5e6b8d
Create Date: 2026-03-02

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# ==========================================================
# Revision identifiers
# ==========================================================

revision: str = '4b5c6d7e8f9a'
down_revision: Union[str, Sequence[str], None] = '5f1e3b7c9a2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema.

    Best practices applied:
    - Column added with server_default for proper database-level default.
    - Non-nullable column to ensure data integrity.
    - All existing branches default to active status.
    """

    # ==========================================================
    # Add is_active column to branches table
    # ==========================================================
    op.add_column(
        'branches',
        sa.Column(
            'is_active',
            sa.Boolean(),
            nullable=False,
            server_default=sa.true()
        )
    )


def downgrade() -> None:
    """
    Downgrade schema.

    Important:
    - Remove the is_active column from branches table.
    """

    op.drop_column('branches', 'is_active')
