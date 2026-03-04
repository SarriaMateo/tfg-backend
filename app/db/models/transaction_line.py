from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Integer, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.item import Item
    from app.db.models.transaction import Transaction


class TransactionLine(Base):
    __tablename__ = "transaction_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("items.id"),
        nullable=False
    )
    transaction_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("transactions.id"),
        nullable=False
    )

    # Relationships
    item: Mapped["Item"] = relationship(back_populates="transaction_lines")
    transaction: Mapped["Transaction"] = relationship(back_populates="lines")
