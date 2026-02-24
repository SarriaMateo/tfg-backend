from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.models.association import item_categories

if TYPE_CHECKING:
    from app.db.models.company import Company
    from app.db.models.item import Item

class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    color: Mapped[str] = mapped_column(String(7), nullable=False)
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("companies.id"),
        nullable=False
    )

    company: Mapped["Company"] = relationship(back_populates="categories")
    items: Mapped[list["Item"]] = relationship(
        secondary=item_categories,
        back_populates="categories"
    )
