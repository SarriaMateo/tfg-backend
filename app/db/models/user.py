# app/db/models/user.py
from __future__ import annotations

import uuid
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, ForeignKey, String, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.branch import Branch
    from app.db.models.company import Company

class Role(PyEnum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    EMPLOYEE = "EMPLOYEE"

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    username: Mapped[str] = mapped_column(String(50),nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Role] = mapped_column(
        SAEnum(Role, name="user_role"),
        nullable=False,
        default=Role.EMPLOYEE,
    )
    company_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("companies.id"),
        nullable=False
    )
    branch_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("branches.id"),
        nullable=True
    )

    company: Mapped["Company"] = relationship(
        back_populates="users"
    )

    branch: Mapped["Branch"] = relationship(
        back_populates="users"
    )