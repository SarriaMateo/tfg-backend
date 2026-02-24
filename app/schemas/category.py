from pydantic import BaseModel, Field
from typing import Optional


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    color: str = Field(min_length=7, max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$")


class CategoryUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    color: Optional[str] = Field(None, min_length=7, max_length=7, pattern=r"^#[0-9A-Fa-f]{6}$")


class CategoryResponse(BaseModel):
    id: int
    name: str
    color: str
    company_id: int

    class Config:
        from_attributes = True
