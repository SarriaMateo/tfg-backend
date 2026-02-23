"""Initial migration

Revision ID: dd7b70a9cf2d
Revises: 
Create Date: 2026-02-05

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# ==========================================================
# Revision identifiers
# ==========================================================

revision: str = 'dd7b70a9cf2d'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Upgrade schema.

    Best practices applied:
    - All constraints have explicit names.
    - Correct creation order according to dependencies.
    - Constraints declared explicitly to facilitate future drop/alter operations.
    """

    # ==========================================================
    # Table: companies
    # ==========================================================
    op.create_table(
        'companies',

        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('nif', sa.String(length=9), nullable=True),

        sa.PrimaryKeyConstraint('id', name='pk_companies'),

        # UNIQUE with explicit name
        sa.UniqueConstraint('email', name='uq_companies_email'),
        sa.UniqueConstraint('nif', name='uq_companies_nif')
    )

    # ==========================================================
    # Table: branches
    # Depends on companies
    # ==========================================================
    op.create_table(
        'branches',

        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('address', sa.String(length=250), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),

        sa.PrimaryKeyConstraint('id', name='pk_branches'),

        # FK with explicit name (CRITICAL for MySQL)
        sa.ForeignKeyConstraint(
            ['company_id'],
            ['companies.id'],
            name='fk_branches_company_id'
        )
    )

    # ==========================================================
    # Table: users
    # Depends on companies and branches
    # ==========================================================
    op.create_table(
        'users',

        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),

        # ENUM in MySQL → if modified requires manual migration afterwards
        sa.Column(
            'role',
            sa.Enum('ADMIN', 'MANAGER', 'EMPLOYEE', name='user_role'),
            nullable=False
        ),

        sa.Column('company_id', sa.Integer(), nullable=False),
        sa.Column('branch_id', sa.Integer(), nullable=True),

        sa.PrimaryKeyConstraint('id', name='pk_users'),

        sa.UniqueConstraint('username', name='uq_users_username'),

        # Explicit FKs
        sa.ForeignKeyConstraint(
            ['company_id'],
            ['companies.id'],
            name='fk_users_company_id'
        ),
        sa.ForeignKeyConstraint(
            ['branch_id'],
            ['branches.id'],
            name='fk_users_branch_id'
        )
    )


def downgrade() -> None:
    """
    Downgrade schema.

    Important:
    - Order must be reverse of creation.
    - Drop most dependent tables first.
    """

    op.drop_table('users')
    op.drop_table('branches')
    op.drop_table('companies')