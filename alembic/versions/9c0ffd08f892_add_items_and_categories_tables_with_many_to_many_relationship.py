"""Add items and categories tables with many-to-many relationship

Revision ID: 9c0ffd08f892
Revises: dd7b70a9cf2d
Create Date: 2026-02-23

"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# ==========================================================
# Revision identifiers
# ==========================================================

revision: str = '9c0ffd08f892'
down_revision: Union[str, Sequence[str], None] = 'dd7b70a9cf2d'
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
    # Table: items
    # Depends on companies
    # ==========================================================
    op.create_table(
        'items',

        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('sku', sa.String(length=12), nullable=False),
        sa.Column(
            'unit',
            sa.String(length=10),
            nullable=False,
            comment='Enum: ud, kg, g, l, ml, m, box, pack'
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('price', sa.Numeric(10, 2), nullable=True),
        sa.Column('brand', sa.String(length=100), nullable=True),
        sa.Column('image_url', sa.String(length=255), nullable=True),
        sa.Column('company_id', sa.Integer(), nullable=False),

        sa.PrimaryKeyConstraint('id', name='pk_items'),

        # FK with explicit name
        sa.ForeignKeyConstraint(
            ['company_id'],
            ['companies.id'],
            name='fk_items_company_id'
        )
    )

    # ==========================================================
    # Table: categories
    # Depends on companies
    # ==========================================================
    op.create_table(
        'categories',

        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('color', sa.String(length=7), nullable=False),
        sa.Column('company_id', sa.Integer(), nullable=False),

        sa.PrimaryKeyConstraint('id', name='pk_categories'),

        # FK with explicit name
        sa.ForeignKeyConstraint(
            ['company_id'],
            ['companies.id'],
            name='fk_categories_company_id'
        )
    )

    # ==========================================================
    # Table: item_categories (Association table for n:m relationship)
    # Depends on items and categories
    # ==========================================================
    op.create_table(
        'item_categories',

        sa.Column('item_id', sa.Integer(), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=False),

        sa.PrimaryKeyConstraint('item_id', 'category_id', name='pk_item_categories'),

        # FKs with explicit names
        sa.ForeignKeyConstraint(
            ['item_id'],
            ['items.id'],
            name='fk_item_categories_item_id'
        ),
        sa.ForeignKeyConstraint(
            ['category_id'],
            ['categories.id'],
            name='fk_item_categories_category_id'
        )
    )


def downgrade() -> None:
    """
    Downgrade schema.

    Important:
    - Order must be reverse of creation.
    - Drop most dependent tables first (item_categories before items/categories).
    - Drop items and categories before dropping the association table.
    """

    op.drop_table('item_categories')
    op.drop_table('categories')
    op.drop_table('items')
