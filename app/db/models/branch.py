# app/db/models/branch.py
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.company import Company
    from app.db.models.user import User
    from app.db.models.stock_movement import StockMovement

class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    address: Mapped[str] = mapped_column(String(250), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        nullable=False,
        default=True,
    )
    company_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("companies.id"),
        nullable=False
    )

    users: Mapped[list["User"]] = relationship(
        back_populates="branch"
    )

    company: Mapped["Company"] = relationship(
        back_populates="branches"
    )
    
    stock_movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="branch",
        cascade="all, delete-orphan"
    )
