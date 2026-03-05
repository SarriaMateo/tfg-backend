from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Integer, DateTime, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.transaction import Transaction
    from app.db.models.user import User


class ActionType(PyEnum):
    CREATED = "CREATED"
    EDITED = "EDITED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class TransactionEvent(Base):
    __tablename__ = "transaction_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action_type: Mapped[ActionType] = mapped_column(
        SAEnum(ActionType, name="action_type", native_enum=False),
        nullable=False
    )
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    event_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    transaction_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("transactions.id"),
        nullable=False
    )
    performed_by: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    # Relationships
    transaction: Mapped["Transaction"] = relationship(back_populates="events")
    user: Mapped["User"] = relationship()
