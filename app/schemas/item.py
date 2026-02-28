from pydantic import BaseModel, Field, field_validator
from enum import Enum
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
import re


class ItemUnit(str, Enum):
    UNIT = "ud"
    KILOGRAM = "kg"
    GRAM = "g"
    LITER = "l"
    MILLILITER = "ml"
    METER = "m"
    BOX = "box"
    PACK = "pack"


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    sku: str = Field(min_length=1, max_length=12)
    unit: ItemUnit
    description: Optional[str] = Field(None, max_length=500)
    price: Optional[Decimal] = Field(None, ge=0, max_digits=10, decimal_places=2)
    brand: Optional[str] = Field(None, max_length=100)
    image_url: Optional[str] = Field(None, max_length=255)

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, value: str) -> str:
        if not re.match(r"^[a-zA-Z0-9]+$", value):
            raise ValueError("SKU must be alphanumeric")
        return value

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is not None and value < 0:
            raise ValueError("Price cannot be negative")
        return value


class ItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    sku: Optional[str] = Field(None, min_length=1, max_length=12)
    unit: Optional[ItemUnit] = None
    description: Optional[str] = Field(None, max_length=500)
    price: Optional[Decimal] = Field(None, ge=0, max_digits=10, decimal_places=2)
    brand: Optional[str] = Field(None, max_length=100)
    image_url: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None

    @field_validator("sku")
    @classmethod
    def validate_sku(cls, value: Optional[str]) -> Optional[str]:
        if value is not None and not re.match(r"^[a-zA-Z0-9]+$", value):
            raise ValueError("SKU must be alphanumeric")
        return value

    @field_validator("price")
    @classmethod
    def validate_price(cls, value: Optional[Decimal]) -> Optional[Decimal]:
        if value is not None and value < 0:
            raise ValueError("Price cannot be negative")
        return value


class ItemResponse(BaseModel):
    id: int
    name: str
    sku: str
    unit: ItemUnit
    created_at: datetime
    is_active: bool
    description: Optional[str]
    price: Optional[Decimal]
    brand: Optional[str]
    image_url: Optional[str]
    company_id: int

    class Config:
        from_attributes = True


class BranchStock(BaseModel):
    """Stock information for a specific branch"""
    branch_id: int
    branch_name: str
    stock: Decimal = Field(default=Decimal("0.000"), max_digits=10, decimal_places=3)

    class Config:
        from_attributes = True


class ItemWithStock(BaseModel):
    """Item with stock information per branch"""
    id: int
    name: str
    sku: str
    unit: ItemUnit
    created_at: datetime
    is_active: bool
    description: Optional[str]
    price: Optional[Decimal]
    brand: Optional[str]
    image_url: Optional[str]
    company_id: int
    stock_by_branch: List[BranchStock] = Field(default_factory=list)

    class Config:
        from_attributes = True
