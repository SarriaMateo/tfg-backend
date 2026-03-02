from pydantic import BaseModel, Field
from typing import Optional


class BranchCreate(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    address: str = Field(min_length=5, max_length=250)


class BranchUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=3, max_length=100)
    address: Optional[str] = Field(None, min_length=5, max_length=250)
    is_active: Optional[bool] = None


class BranchResponse(BaseModel):
    id: int
    name: str
    address: str
    is_active: bool
    company_id: int

    class Config:
        from_attributes = True
