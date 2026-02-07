from pydantic import BaseModel, EmailStr, Field, field_validator
from enum import Enum
from typing import Optional
import re


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    EMPLOYEE = "EMPLOYEE"


class AdminUserCreate(BaseModel):
    name: str = Field(min_length=3, max_length=50)
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        if " " in value:
            raise ValueError("Username cannot contain spaces")
        if not re.match(r"^[a-zA-Z0-9._-]+$", value):
            raise ValueError("Username can only contain letters, numbers, dots, hyphens and underscores")
        return value


class UserResponse(BaseModel):
    id: int
    name: str
    username: str
    role: UserRole
    company_id: int
    branch_id: Optional[int]

    class Config:
        from_attributes = True
