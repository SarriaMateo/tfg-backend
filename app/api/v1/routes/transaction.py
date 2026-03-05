from fastapi import APIRouter, Depends, UploadFile, File, status, Form, Query, Request
from starlette.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional, Literal, List
from decimal import Decimal

from app.db.session import get_db
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdate,
    TransactionResponse,
    TransactionDetailResponse,
    TransactionLineCreate,
    OperationType,
    TransactionStatus
)
from app.schemas.common import PaginatedResponse
from app.core.security import get_current_user
from app.db.models.user import User
from app.services.transaction.transaction_service import TransactionService
from app.repositories.transaction_repository import TransactionRepository
import math

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get(
    "",
    response_model=PaginatedResponse[TransactionResponse],
    status_code=status.HTTP_200_OK
)
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    branch_id: Optional[int] = Query(None, ge=1),
    operation_type: Optional[OperationType] = Query(None),
    status: Optional[TransactionStatus] = Query(None),
    performed_by: Optional[int] = Query(None, ge=1),
    item_id: Optional[int] = Query(None, ge=1),
    search: Optional[str] = Query(None),
    order_by: Literal["created_at", "total_items"] = Query("created_at"),
    order_desc: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List transactions for the user's company with filtering, search, sorting, and pagination.
    If user has assigned branch, only shows transactions from that branch.
    
    Filters:
    - branch_id: Filter by branch
    - operation_type: Filter by operation type (IN, OUT, TRANSFER, ADJUSTMENT)
    - status: Filter by status (PENDING, CANCELLED, COMPLETED)
    - performed_by: Filter by user who performed action
    - item_id: Filter by item in transaction lines
    - search: Search in item names and SKUs
    
    Ordering:
    - order_by: "created_at" or "total_items"
    - order_desc: True for descending, False for ascending
    """
    transactions, total = TransactionService.list_transactions(
        db=db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        branch_id=branch_id,
        operation_type=operation_type,
        status=status,
        performed_by=performed_by,
        item_id=item_id,
        search=search,
        order_by=order_by,
        order_desc=order_desc
    )
    
    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 0
    
    return PaginatedResponse(
        data=transactions,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED
)
def create_transaction(
    transaction_data: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new transaction (IN or OUT only for now).
    
    Validations:
    - Operation type must be IN or OUT (TRANSFER and ADJUSTMENT not supported yet)
    - Branch must be active and belong to user's company
    - If user has branch assigned, can only create in that branch
    - All items must be active and belong to same company
    - Quantities must be integers for units: ud, box, pack
    
    Actions:
    - Creates transaction record
    - Creates transaction lines
    - Creates CREATED event
    """
    transaction = TransactionService.create_transaction(db, transaction_data, current_user)
    return transaction


@router.get(
    "/{transaction_id}",
    response_model=TransactionDetailResponse,
    status_code=status.HTTP_200_OK
)
def get_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a transaction by ID with full details including events.
    User can only view transactions from their accessible branches.
    """
    transaction = TransactionService.get_transaction(db, transaction_id, current_user)
    return transaction


@router.put(
    "/{transaction_id}",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK
)
def update_transaction(
    transaction_id: int,
    description: Optional[str] = Form(None),
    lines_json: Optional[str] = Form(None),  # JSON string of lines
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a transaction (only if status is PENDING).
    
    Validations:
    - Transaction must exist and belong to user's accessible branches
    - Transaction must be in PENDING status
    - If items are updated, same validations as create
    
    Actions:
    - Updates transaction fields
    - Updates transaction lines if provided
    - Creates EDITED event with metadata showing changes
    
    Note: lines_json should be a JSON array like: [{"quantity": 10.5, "item_id": 1}, ...]
    """
    import json
    from app.schemas.transaction import TransactionLineCreate
    
    # Build update data
    update_data = TransactionUpdate(description=description)
    
    # Parse lines if provided
    new_lines = None
    if lines_json:
        lines_data = json.loads(lines_json)
        new_lines = [TransactionLineCreate(**line) for line in lines_data]
    
    transaction = TransactionService.update_transaction(
        db, transaction_id, update_data, current_user, new_lines
    )
    return transaction


@router.post(
    "/{transaction_id}/cancel",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK
)
def cancel_transaction(
    transaction_id: int,
    cancel_reason: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cancel a transaction (only if status is PENDING).
    
    Validations:
    - Transaction must exist and belong to user's accessible branches
    - Transaction must be in PENDING status
    
    Actions:
    - Updates status to CANCELLED
    - Creates CANCELLED event with optional reason in metadata
    - Transaction cannot be modified after cancellation
    """
    transaction = TransactionService.cancel_transaction(
        db, transaction_id, current_user, cancel_reason
    )
    return transaction


@router.post(
    "/{transaction_id}/complete",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK
)
def complete_transaction(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Complete a transaction (only if status is PENDING).
    
    Validations:
    - Transaction must exist and belong to user's accessible branches
    - Transaction must be in PENDING status
    - For OUT operations, verifies stock won't go negative
    
    Actions:
    - Updates status to COMPLETED
    - Creates stock_movements for each line (IN = positive, OUT = negative)
    - Creates COMPLETED event
    - Transaction cannot be modified after completion
    """
    transaction = TransactionService.complete_transaction(
        db, transaction_id, current_user
    )
    return transaction


@router.post(
    "/{transaction_id}/document",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK
)
async def upload_document(
    transaction_id: int,
    document: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Upload a document to a transaction.
    Only allowed if transaction is in PENDING status.
    
    Supported formats: PDF, Word, Excel, Images (JPG, PNG, WebP)
    Maximum size: 10MB
    """
    document_file = await document.read()
    document_filename = document.filename
    
    transaction = TransactionService.upload_document(
        db, transaction_id, current_user, document_file, document_filename
    )
    return transaction


@router.get(
    "/{transaction_id}/document",
    status_code=status.HTTP_200_OK
)
def get_document(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get the document file for a transaction.
    Returns the document file if it exists, 404 otherwise.
    """
    import mimetypes
    
    document_path = TransactionService.get_document(db, transaction_id, current_user)
    
    # Determine media type from file extension
    media_type, _ = mimetypes.guess_type(str(document_path))
    if not media_type:
        media_type = "application/octet-stream"
    
    return FileResponse(path=document_path, media_type=media_type)


@router.delete(
    "/{transaction_id}/document",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK
)
def delete_document(
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete the document from a transaction.
    Only allowed if transaction is in PENDING status.
    """
    transaction = TransactionService.delete_document(db, transaction_id, current_user)
    return transaction
