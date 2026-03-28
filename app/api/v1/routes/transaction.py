from fastapi import APIRouter, Depends, UploadFile, File, status, Query, Request
from starlette.responses import FileResponse
from fastapi.responses import Response
from sqlalchemy.orm import Session
from typing import Optional, Literal, List
from decimal import Decimal
from datetime import date

from app.db.session import get_db
from app.schemas.transaction import (
    TransactionCreate,
    TransactionUpdateRequest,
    TransactionCancelRequest,
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
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
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
    - branch_id: Filter by branch as origin or as destination
    - operation_type: Filter by operation type (IN, OUT, TRANSFER, ADJUSTMENT)
    - status: Filter by status (PENDING, CANCELLED, COMPLETED)
    - performed_by: Filter by user who performed action
    - item_id: Filter by item in transaction lines
    - start_date: Filter transactions created on/after this date
    - end_date: Filter transactions created on/before this date
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
        start_date=start_date,
        end_date=end_date,
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


@router.get(
    "/export",
    status_code=status.HTTP_200_OK
)
def export_transactions(
    export_format: Literal["csv", "pdf"] = Query("csv", alias="format"),
    branch_id: Optional[int] = Query(None, ge=1),
    operation_type: Optional[OperationType] = Query(None),
    status: Optional[TransactionStatus] = Query(None),
    performed_by: Optional[int] = Query(None, ge=1),
    item_id: Optional[int] = Query(None, ge=1),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    search: Optional[str] = Query(None),
    order_by: Literal["created_at", "total_items"] = Query("created_at"),
    order_desc: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export transactions using the same filters/search/sorting as listing.
    """
    csv_bytes, filename = TransactionService.export_transactions_csv(
        db=db,
        current_user=current_user,
        export_format=export_format,
        branch_id=branch_id,
        operation_type=operation_type,
        status_filter=status,
        performed_by=performed_by,
        item_id=item_id,
        start_date=start_date,
        end_date=end_date,
        search=search,
        order_by=order_by,
        order_desc=order_desc,
    )

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
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
    Create a new transaction.
    
    Validations:
    - Operation type supports IN, OUT, TRANSFER and ADJUSTMENT
    - ADJUSTMENT requires ADMIN/MANAGER role, non-empty description and auto_complete=true
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
    User can view transactions from their accessible branches.
    For TRANSFER type, also allows access if user is associated with destination branch.
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
    update_data: TransactionUpdateRequest,
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
    - Updates description and/or lines
    - Creates EDITED event with metadata showing old and new values
    """
    transaction = TransactionService.update_transaction(
        db, transaction_id, update_data, current_user
    )
    return transaction


@router.post(
    "/{transaction_id}/cancel",
    response_model=TransactionResponse,
    status_code=status.HTTP_200_OK
)
def cancel_transaction(
    transaction_id: int,
    cancel_data: TransactionCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cancel a transaction.
    
    Validations:
    - Transaction must exist and belong to user's accessible branches
    - For TRANSFER in PENDING, only origin branch (or central user) can cancel
    - For TRANSFER in TRANSIT, only destination branch (or central user) can cancel
    - Transaction must be in PENDING or TRANSIT status
    
    Actions:
    - Updates status to CANCELLED
    - Creates CANCELLED event with optional reason in metadata
    - Transaction cannot be modified after cancellation
    """
    transaction = TransactionService.cancel_transaction(
        db, transaction_id, current_user, cancel_data.cancel_reason
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
    Complete a transaction.
    
    Validations:
    - Transaction must exist and belong to user's accessible branches
    - For TRANSFER in PENDING, only origin branch (or central user) can send to TRANSIT
    - For TRANSFER in TRANSIT, only destination branch (or central user) can receive to COMPLETED
    - IN/OUT transactions must be in PENDING status
    - TRANSFER transactions move PENDING -> TRANSIT on first completion
    - TRANSFER transactions move TRANSIT -> COMPLETED on second completion
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
    ADMIN/MANAGER: allowed for any transaction status.
    EMPLOYEE: allowed for PENDING, or for COMPLETED/CANCELLED only if they created the transaction.
    
    Supported formats: PDF, Word, Excel, Images (JPG, PNG, WebP)
    Maximum size: 10MB
    """
    document_file = await document.read()
    document_filename = document.filename or "unknown"
    
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
    document_path, media_type, download_name = TransactionService.get_document(
        db, transaction_id, current_user
    )
    return FileResponse(path=document_path, media_type=media_type, filename=download_name)


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
    ADMIN/MANAGER: allowed for any transaction status.
    EMPLOYEE: allowed for PENDING, or for COMPLETED/CANCELLED only if they created the transaction.
    """
    transaction = TransactionService.delete_document(db, transaction_id, current_user)
    return transaction
