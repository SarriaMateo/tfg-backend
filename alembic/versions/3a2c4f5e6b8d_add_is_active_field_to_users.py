"""Add is_active field to users table

Revision ID: 3a2c4f5e6b8d
Revises: 9c0ffd08f892
Create Date: 2026-02-27

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# ==========================================================
# Revision identifiers
# ==========================================================

revision: str = '3a2c4f5e6b8d'
down_revision: Union[str, Sequence[str], None] = '9c0ffd08f892'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema.

    Best practices applied:
    - Column added with server_default for proper database-level default.
    - Non-nullable column to ensure data integrity.
    - All existing users default to active status.
    """

    # ==========================================================
    # Add is_active column to users table
    # ==========================================================
    op.add_column(
        'users',
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
    - Remove the is_active column from users table.
    """

    op.drop_column('users', 'is_active')
