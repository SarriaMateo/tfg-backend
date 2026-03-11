from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from app.db.models.transaction import OperationType, TransactionStatus
from app.db.models.transaction_event import ActionType


class TransactionLineCreate(BaseModel):
    quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=3)
    item_id: int = Field(gt=0)


class TransactionLineResponse(BaseModel):
    id: int
    quantity: Decimal
    item_id: int
    transaction_id: int

    class Config:
        from_attributes = True


class TransactionCreate(BaseModel):
    operation_type: OperationType
    description: Optional[str] = Field(None, max_length=1000)
    branch_id: int = Field(gt=0)
    destination_branch_id: Optional[int] = Field(None, gt=0)
    auto_complete: bool = False
    lines: List[TransactionLineCreate] = Field(min_length=1)

    @field_validator("destination_branch_id")
    @classmethod
    def validate_destination_branch(cls, value: Optional[int], info) -> Optional[int]:
        """Destination branch is required for TRANSFER operations"""
        operation_type = info.data.get("operation_type")
        
        if operation_type == OperationType.TRANSFER and value is None:
            raise ValueError("Destination branch is required for TRANSFER operations")
        
        if operation_type != OperationType.TRANSFER and value is not None:
            raise ValueError("Destination branch can only be set for TRANSFER operations")
        
        return value


class TransactionResponse(BaseModel):
    id: int
    operation_type: OperationType
    status: TransactionStatus
    created_at: datetime
    description: Optional[str]
    document_url: Optional[str] = None
    branch_id: int
    destination_branch_id: Optional[int]
    lines: List[TransactionLineResponse]

    class Config:
        from_attributes = True


class TransactionDetailResponse(BaseModel):
    """Detailed transaction response including events"""
    id: int
    operation_type: OperationType
    status: TransactionStatus
    created_at: datetime
    description: Optional[str]
    document_url: Optional[str] = None
    branch_id: int
    destination_branch_id: Optional[int]
    lines: List[TransactionLineResponse]
    events: List["TransactionEventResponse"]

    class Config:
        from_attributes = True


class TransactionEventResponse(BaseModel):
    id: int
    action_type: ActionType
    timestamp: datetime
    event_metadata: Optional[dict] = None
    transaction_id: int
    performed_by: int

    class Config:
        from_attributes = True


class TransactionUpdateRequest(BaseModel):
    """Payload for PUT /transactions/{id}"""
    description: Optional[str] = Field(None, max_length=1000)
    lines: Optional[List[TransactionLineCreate]] = None


class TransactionUpdate(BaseModel):
    """Update transaction status or description (limited operations)"""
    status: Optional[TransactionStatus] = None
    description: Optional[str] = Field(None, max_length=1000)
