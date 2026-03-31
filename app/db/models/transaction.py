from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Integer, String, DateTime, ForeignKey, Enum as SAEnum, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base
from app.core.datetime_utils import madrid_now

if TYPE_CHECKING:
    from app.db.models.branch import Branch
    from app.db.models.user import User
    from app.db.models.transaction_line import TransactionLine
    from app.db.models.transaction_event import TransactionEvent
    from app.db.models.stock_movement import StockMovement


class OperationType(PyEnum):
    IN = "IN"
    OUT = "OUT"
    TRANSFER = "TRANSFER"
    ADJUSTMENT = "ADJUSTMENT"


class TransactionStatus(PyEnum):
    PENDING = "PENDING"
    TRANSIT = "TRANSIT"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    operation_type: Mapped[OperationType] = mapped_column(
        SAEnum(OperationType, name="operation_type", native_enum=False),
        nullable=False
    )
    status: Mapped[TransactionStatus] = mapped_column(
        SAEnum(TransactionStatus, name="transaction_status", native_enum=False),
        nullable=False,
        default=TransactionStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=madrid_now)
    last_event_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    document_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    branch_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("branches.id"),
        nullable=False
    )
    destination_branch_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("branches.id"),
        nullable=True
    )

    # Relationships
    branch: Mapped["Branch"] = relationship(
        back_populates="transactions",
        foreign_keys=[branch_id]
    )
    destination_branch: Mapped[Optional["Branch"]] = relationship(
        foreign_keys=[destination_branch_id]
    )
    lines: Mapped[list["TransactionLine"]] = relationship(
        back_populates="transaction",
        cascade="all, delete-orphan"
    )
    events: Mapped[list["TransactionEvent"]] = relationship(
        back_populates="transaction",
        cascade="all, delete-orphan"
    )
    stock_movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="transaction",
        cascade="all, delete-orphan"
    )

    @property
    def has_document(self) -> bool:
        return bool(self.document_url)
