from pydantic import BaseModel, Field, field_validator
from enum import Enum
from datetime import datetime
from decimal import Decimal


class MovementType(str, Enum):
    IN = "IN"
    OUT = "OUT"
    TRANSFER = "TRANSFER"
    ADJUSTMENT = "ADJUSTMENT"


class StockMovementCreate(BaseModel):
    quantity: Decimal = Field(max_digits=10, decimal_places=3)
    movement_type: MovementType
    item_id: int = Field(gt=0)
    branch_id: int = Field(gt=0)

    @field_validator("quantity")
    @classmethod
    def validate_quantity(cls, value: Decimal, info) -> Decimal:
        """Validate quantity based on movement type"""
        movement_type = info.data.get("movement_type")
        
        if movement_type == MovementType.IN and value <= 0:
            raise ValueError("Quantity must be positive for IN movements")
        elif movement_type == MovementType.OUT and value >= 0:
            raise ValueError("Quantity must be negative for OUT movements")
        
        return value


class StockMovementResponse(BaseModel):
    id: int
    quantity: Decimal
    movement_type: MovementType
    created_at: datetime
    item_id: int
    branch_id: int

    class Config:
        from_attributes = True
