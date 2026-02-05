# app/db/models/branch.py
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.company import Company
    from app.db.models.user import User

class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    adress: Mapped[str] = mapped_column(String(250), nullable=False)
    company_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("companies.id"),
        nullable=False
    )

    users: Mapped[list["User"]] = relationship(
        back_populates="branch"
    )

    company: Mapped["Company"] = relationship(
        back_populates="branches"
    )
