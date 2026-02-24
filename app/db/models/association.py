"""
Many-to-Many association table for Item-Category relationship
"""

from sqlalchemy import Table, Column, Integer, ForeignKey
from app.db.base import Base

# Explicit definition of the item_categories association table
# This is required for SQLAlchemy 2.0+ to properly resolve many-to-many relationships
item_categories = Table(
    "item_categories",
    Base.metadata,
    Column("item_id", Integer, ForeignKey("items.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", Integer, ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)
