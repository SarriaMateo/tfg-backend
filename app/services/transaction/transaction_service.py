from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional, List, Tuple
from pathlib import Path
from datetime import datetime
from decimal import Decimal

from app.db.models.transaction import Transaction, OperationType, TransactionStatus
from app.db.models.transaction_line import TransactionLine
from app.db.models.transaction_event import TransactionEvent, ActionType
from app.db.models.stock_movement import StockMovement, MovementType
from app.db.models.user import User, Role
from app.db.models.item import Item, Unit
from app.repositories.transaction_repository import TransactionRepository
from app.repositories.item_repository import ItemRepository
from app.repositories.branch_repository import BranchRepository
from app.repositories.stock_movement_repository import StockMovementRepository
from app.schemas.transaction import TransactionCreate, TransactionUpdate
from app.schemas.common import PaginatedResponse
from app.core.file_handler import TransactionDocumentHandler
from app.services.user.user_service import UserService


class TransactionService:
    """Business logic service for transactions (IN and OUT only for now)"""

    @staticmethod
    def _validate_user_can_access_branch(current_user: User, branch_id: int, db: Session) -> None:
        """
        Validate that user can access a specific branch.
        - Branch must exist and be active
        - Branch must belong to user's company
        - If user has assigned branch, can only access that branch
        """
        branch = BranchRepository.get_by_id(db, branch_id)
        if not branch or not branch.is_active:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="BRANCH_NOT_FOUND"
            )
        
        if branch.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="BRANCH_NOT_FOUND"
            )
        
        # If user has assigned branch, can only access that branch
        if current_user.branch_id and current_user.branch_id != branch_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="BRANCH_ACCESS_DENIED"
            )

    @staticmethod
    def _validate_items_belong_to_company(db: Session, item_ids: List[int], company_id: int) -> List[Item]:
        """
        Validate that all items exist, are active, and belong to the company.
        Returns list of Item objects.
        """
        items = []
        for item_id in item_ids:
            item = ItemRepository.get_by_id(db, item_id)
            if not item or not item.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"ITEM_NOT_FOUND"
                )
            
            if item.company_id != company_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="ITEM_NOT_FOUND"
                )
            
            items.append(item)
        
        return items

    @staticmethod
    def _validate_quantities_for_units(lines_data: List, items: List[Item]) -> None:
        """
        Validate that quantities are integers for units: ud, box, pack.
        """
        for idx, line_data in enumerate(lines_data):
            item = items[idx]
            if item.unit in (Unit.UNIT, Unit.BOX, Unit.PACK):
                if line_data.quantity % 1 != 0:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"QUANTITY_MUST_BE_INTEGER_FOR_UNIT_{item.unit.value}"
                    )

    @staticmethod
    def _validate_transaction_editable(transaction: Transaction) -> None:
        """
        Validate that transaction can be edited (status must be PENDING).
        """
        if transaction.status != TransactionStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="TRANSACTION_NOT_EDITABLE"
            )

    @staticmethod
    def create_transaction(
        db: Session,
        transaction_data: TransactionCreate,
        current_user: User
    ) -> Transaction:
        """
        Create a new transaction (IN or OUT only).
        
        Validations:
        - User must be active
        - Operation type must be IN or OUT (TRANSFER and ADJUSTMENT not implemented yet)
        - Branch must be active and belong to user's company
        - If user has branch assigned, can only create in that branch
        - All items must be active and belong to same company
        - Quantities must be integers for units: ud, box, pack
        
        Actions:
        - Create transaction record
        - Create transaction lines
        - Create CREATED event
        """
        UserService.validate_user_active(current_user)
        
        # Validate operation type (only IN and OUT for now)
        if transaction_data.operation_type not in (OperationType.IN, OperationType.OUT):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OPERATION_TYPE_NOT_SUPPORTED"
            )
        
        # Validate branch access
        TransactionService._validate_user_can_access_branch(
            current_user, transaction_data.branch_id, db
        )
        
        # Validate items
        item_ids = [line.item_id for line in transaction_data.lines]
        items = TransactionService._validate_items_belong_to_company(
            db, item_ids, current_user.company_id
        )
        
        # Validate quantities for specific units
        TransactionService._validate_quantities_for_units(transaction_data.lines, items)
        
        # Create transaction
        transaction = Transaction(
            operation_type=transaction_data.operation_type,
            status=TransactionStatus.PENDING,
            description=transaction_data.description,
            branch_id=transaction_data.branch_id,
            destination_branch_id=transaction_data.destination_branch_id,
            created_at=datetime.utcnow()
        )
        TransactionRepository.create(db, transaction)
        
        # Create transaction lines
        for line_data in transaction_data.lines:
            line = TransactionLine(
                quantity=line_data.quantity,
                item_id=line_data.item_id,
                transaction_id=transaction.id
            )
            TransactionRepository.create_line(db, line)
        
        # Create CREATED event
        event = TransactionEvent(
            action_type=ActionType.CREATED,
            timestamp=datetime.utcnow(),
            transaction_id=transaction.id,
            performed_by=current_user.id
        )
        TransactionRepository.create_event(db, event)
        
        TransactionRepository.commit(db)
        
        # Refresh to get lines and events
        db.refresh(transaction)
        return transaction

    @staticmethod
    def update_transaction(
        db: Session,
        transaction_id: int,
        transaction_data: TransactionUpdate,
        current_user: User,
        new_lines: Optional[List] = None
    ) -> Transaction:
        """
        Update a transaction (only if status is PENDING).
        
        Validations:
        - User must be active
        - Transaction must exist and belong to user's accessible branches
        - Transaction must be in PENDING status
        - If items are updated, same validations as create
        
        Actions:
        - Update transaction fields
        - Update transaction lines if provided
        - Create EDITED event with metadata showing changes
        """
        UserService.validate_user_active(current_user)
        
        # Get transaction
        transaction = TransactionRepository.get_by_id(db, transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TRANSACTION_NOT_FOUND"
            )
        
        # Validate access
        TransactionService._validate_user_can_access_branch(
            current_user, transaction.branch_id, db
        )
        
        # Validate editable
        TransactionService._validate_transaction_editable(transaction)
        
        # Track changes for metadata
        changes = {}
        
        # Update fields
        if transaction_data.description is not None:
            if transaction.description != transaction_data.description:
                changes["description"] = {
                    "previous": transaction.description,
                    "new": transaction_data.description
                }
            transaction.description = transaction_data.description
        
        # Update lines if provided
        if new_lines is not None:
            # Validate items
            item_ids = [line.item_id for line in new_lines]
            items = TransactionService._validate_items_belong_to_company(
                db, item_ids, current_user.company_id
            )
            
            # Validate quantities
            TransactionService._validate_quantities_for_units(new_lines, items)
            
            # Delete old lines
            for old_line in transaction.lines:
                db.delete(old_line)
            
            # Create new lines
            for line_data in new_lines:
                line = TransactionLine(
                    quantity=line_data.quantity,
                    item_id=line_data.item_id,
                    transaction_id=transaction.id
                )
                TransactionRepository.create_line(db, line)
            
            changes["lines"] = "updated"
        
        TransactionRepository.update(db, transaction)
        
        # Create EDITED event
        event = TransactionEvent(
            action_type=ActionType.EDITED,
            timestamp=datetime.utcnow(),
            transaction_id=transaction.id,
            performed_by=current_user.id,
            event_metadata=changes
        )
        TransactionRepository.create_event(db, event)
        
        TransactionRepository.commit(db)
        
        db.refresh(transaction)
        return transaction

    @staticmethod
    def cancel_transaction(
        db: Session,
        transaction_id: int,
        current_user: User,
        cancel_reason: Optional[str] = None
    ) -> Transaction:
        """
        Cancel a transaction (only if status is PENDING).
        
        Validations:
        - User must be active
        - Transaction must exist and belong to user's accessible branches
        - Transaction must be in PENDING status
        
        Actions:
        - Update status to CANCELLED
        - Create CANCELLED event with optional reason in metadata
        """
        UserService.validate_user_active(current_user)
        
        # Get transaction
        transaction = TransactionRepository.get_by_id(db, transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TRANSACTION_NOT_FOUND"
            )
        
        # Validate access
        TransactionService._validate_user_can_access_branch(
            current_user, transaction.branch_id, db
        )
        
        # Validate editable
        TransactionService._validate_transaction_editable(transaction)
        
        # Update status
        transaction.status = TransactionStatus.CANCELLED
        TransactionRepository.update(db, transaction)
        
        # Create CANCELLED event
        metadata = None
        if cancel_reason:
            metadata = {"reason": cancel_reason}
        
        event = TransactionEvent(
            action_type=ActionType.CANCELLED,
            timestamp=datetime.utcnow(),
            transaction_id=transaction.id,
            performed_by=current_user.id,
            event_metadata=metadata
        )
        TransactionRepository.create_event(db, event)
        
        TransactionRepository.commit(db)
        
        db.refresh(transaction)
        return transaction

    @staticmethod
    def complete_transaction(
        db: Session,
        transaction_id: int,
        current_user: User
    ) -> Transaction:
        """
        Complete a transaction (only if status is PENDING).
        
        Validations:
        - User must be active
        - Transaction must exist and belong to user's accessible branches
        - Transaction must be in PENDING status
        - For OUT operations, verify stock won't go negative
        
        Actions:
        - Update status to COMPLETED
        - Create stock_movements for each line (IN = positive, OUT = negative)
        - Create COMPLETED event
        """
        UserService.validate_user_active(current_user)
        
        # Get transaction with lines
        transaction = TransactionRepository.get_by_id(db, transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TRANSACTION_NOT_FOUND"
            )
        
        # Validate access
        TransactionService._validate_user_can_access_branch(
            current_user, transaction.branch_id, db
        )
        
        # Validate editable
        TransactionService._validate_transaction_editable(transaction)
        
        # For OUT operations, validate stock won't go negative
        if transaction.operation_type == OperationType.OUT:
            for line in transaction.lines:
                current_stock = StockMovementRepository.get_stock_by_item_and_branch(
                    db, line.item_id, transaction.branch_id
                )
                
                if current_stock - line.quantity < 0:
                    item = ItemRepository.get_by_id(db, line.item_id)
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"INSUFFICIENT_STOCK_FOR_ITEM_{item.sku}"
                    )
        
        # Update status
        transaction.status = TransactionStatus.COMPLETED
        TransactionRepository.update(db, transaction)
        
        # Create stock movements
        for line in transaction.lines:
            # IN = positive, OUT = negative
            quantity = line.quantity if transaction.operation_type == OperationType.IN else -line.quantity
            
            stock_movement = StockMovement(
                quantity=quantity,
                movement_type=MovementType(transaction.operation_type.value),
                created_at=datetime.utcnow(),
                item_id=line.item_id,
                branch_id=transaction.branch_id,
                transaction_id=transaction.id
            )
            db.add(stock_movement)
        
        # Create COMPLETED event
        event = TransactionEvent(
            action_type=ActionType.COMPLETED,
            timestamp=datetime.utcnow(),
            transaction_id=transaction.id,
            performed_by=current_user.id
        )
        TransactionRepository.create_event(db, event)
        
        TransactionRepository.commit(db)
        
        db.refresh(transaction)
        return transaction

    @staticmethod
    def get_transaction(
        db: Session,
        transaction_id: int,
        current_user: User
    ) -> Transaction:
        """
        Get a transaction by ID.
        User can only view transactions from their accessible branches.
        """
        UserService.validate_user_active(current_user)
        
        transaction = TransactionRepository.get_by_id(db, transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TRANSACTION_NOT_FOUND"
            )
        
        # Validate access
        TransactionService._validate_user_can_access_branch(
            current_user, transaction.branch_id, db
        )
        
        return transaction

    @staticmethod
    def list_transactions(
        db: Session,
        current_user: User,
        page: int = 1,
        page_size: int = 20,
        branch_id: Optional[int] = None,
        operation_type: Optional[OperationType] = None,
        status: Optional[TransactionStatus] = None,
        performed_by: Optional[int] = None,
        item_id: Optional[int] = None,
        search: Optional[str] = None,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> Tuple[List[Transaction], int]:
        """
        List transactions for the user's company with filters.
        If user has assigned branch, only show transactions from that branch.
        """
        UserService.validate_user_active(current_user)
        
        # If user has assigned branch, override branch_id filter
        if current_user.branch_id:
            branch_id = current_user.branch_id
        
        transactions, total = TransactionRepository.list_transactions(
            db=db,
            company_id=current_user.company_id,
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
        
        return transactions, total

    @staticmethod
    def upload_document(
        db: Session,
        transaction_id: int,
        current_user: User,
        document_file: bytes,
        document_filename: str
    ) -> Transaction:
        """
        Upload a document to a transaction.
        Only allowed if transaction is in PENDING status.
        """
        UserService.validate_user_active(current_user)
        
        # Get transaction
        transaction = TransactionRepository.get_by_id(db, transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TRANSACTION_NOT_FOUND"
            )
        
        # Validate access
        TransactionService._validate_user_can_access_branch(
            current_user, transaction.branch_id, db
        )
        
        # Validate editable
        TransactionService._validate_transaction_editable(transaction)
        
        # Delete old document if exists
        if transaction.document_url:
            TransactionDocumentHandler.delete_document(transaction.document_url)
        
        # Save new document
        document_url = TransactionDocumentHandler.save_document(
            document_file, document_filename, current_user.company_id
        )
        
        transaction.document_url = document_url
        TransactionRepository.update(db, transaction)
        TransactionRepository.commit(db)
        
        return transaction

    @staticmethod
    def get_document(
        db: Session,
        transaction_id: int,
        current_user: User
    ) -> Path:
        """
        Get the document file path for a transaction.
        Similar to ItemService.get_item_image.
        """
        UserService.validate_user_active(current_user)
        
        transaction = TransactionRepository.get_by_id(db, transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TRANSACTION_NOT_FOUND"
            )
        
        # Validate access
        TransactionService._validate_user_can_access_branch(
            current_user, transaction.branch_id, db
        )
        
        if not transaction.document_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DOCUMENT_NOT_FOUND"
            )
        
        file_path = TransactionDocumentHandler.get_absolute_path(transaction.document_url)
        if not file_path or not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="DOCUMENT_NOT_FOUND"
            )
        
        return file_path

    @staticmethod
    def delete_document(
        db: Session,
        transaction_id: int,
        current_user: User
    ) -> Transaction:
        """
        Delete the document from a transaction.
        Only allowed if transaction is in PENDING status.
        """
        UserService.validate_user_active(current_user)
        
        # Get transaction
        transaction = TransactionRepository.get_by_id(db, transaction_id)
        if not transaction:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="TRANSACTION_NOT_FOUND"
            )
        
        # Validate access
        TransactionService._validate_user_can_access_branch(
            current_user, transaction.branch_id, db
        )
        
        # Validate editable
        TransactionService._validate_transaction_editable(transaction)
        
        if transaction.document_url:
            TransactionDocumentHandler.delete_document(transaction.document_url)
            transaction.document_url = None
            TransactionRepository.update(db, transaction)
            TransactionRepository.commit(db)
        
        return transaction
