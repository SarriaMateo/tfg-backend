from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, Enum as SAEnum, Numeric, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.db.models.association import item_categories
from app.core.datetime_utils import madrid_now

if TYPE_CHECKING:
    from app.db.models.company import Company
    from app.db.models.category import Category
    from app.db.models.stock_movement import StockMovement
    from app.db.models.transaction_line import TransactionLine

class Unit(PyEnum):
    UNIT = "ud"
    KILOGRAM = "kg"
    GRAM = "g"
    LITER = "l"
    MILLILITER = "ml"
    METER = "m"
    SQ_METER = "m2"
    BOX = "box"
    PACK = "pack"

class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    sku: Mapped[str] = mapped_column(String(12), nullable=False)
    unit: Mapped[Unit] = mapped_column(
        SAEnum(Unit, name="item_unit", native_enum=False),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=madrid_now)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    image_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    low_stock_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default=text("0")
    )
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("companies.id"),
        nullable=False
    )

    company: Mapped["Company"] = relationship(back_populates="items")
    categories: Mapped[list["Category"]] = relationship(
        secondary=item_categories,
        back_populates="items"
    )
    stock_movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan"
    )
    transaction_lines: Mapped[list["TransactionLine"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan"
    )

    @property
    def has_image(self) -> bool:
        return bool(self.image_url)
