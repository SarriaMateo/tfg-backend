from pydantic import BaseModel, EmailStr, Field
from enum import Enum
from typing import Optional


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    EMPLOYEE = "EMPLOYEE"


class AdminUserCreate(BaseModel):
    name: str
    username: str
    password: str = Field(min_length=8, max_length=72)


class UserResponse(BaseModel):
    id: int
    name: str
    username: str
    role: UserRole
    company_id: int
    branch_id: Optional[int]

    class Config:
        from_attributes = True
