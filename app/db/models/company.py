# app/db/models/company.py
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.branch import Branch
    from app.db.models.user import User

class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    nif: Mapped[Optional[str]] = mapped_column(String(9), unique=True, nullable=True)

    users: Mapped[list["User"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan"
    )

    branches: Mapped[list["Branch"]] = relationship(
        back_populates="company",
        cascade="all, delete-orphan"
    )