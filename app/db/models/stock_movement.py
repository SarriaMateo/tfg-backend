from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import Integer, DateTime, ForeignKey, Enum as SAEnum, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.core.datetime_utils import madrid_now

if TYPE_CHECKING:
    from app.db.models.item import Item
    from app.db.models.branch import Branch
    from app.db.models.transaction import Transaction


class MovementType(PyEnum):
    IN = "IN"
    OUT = "OUT"
    TRANSFER = "TRANSFER"
    ADJUSTMENT = "ADJUSTMENT"


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    movement_type: Mapped[MovementType] = mapped_column(
        SAEnum(MovementType, name="movement_type", native_enum=False),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=madrid_now)
    item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("items.id"),
        nullable=False
    )
    branch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("branches.id"),
        nullable=False
    )
    transaction_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("transactions.id"),
        nullable=False
    )

    # Relationships
    item: Mapped["Item"] = relationship(back_populates="stock_movements")
    branch: Mapped["Branch"] = relationship(back_populates="stock_movements")
    transaction: Mapped["Transaction"] = relationship(back_populates="stock_movements")
