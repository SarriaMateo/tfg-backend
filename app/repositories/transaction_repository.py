from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, desc, asc
from typing import Optional, Tuple, List
from datetime import date, datetime, time
from app.db.models.transaction import Transaction, OperationType, TransactionStatus
from app.db.models.transaction_line import TransactionLine
from app.db.models.transaction_event import TransactionEvent
from app.db.models.branch import Branch
from app.db.models.item import Item


class TransactionRepository:
    """Repository for transaction management"""

    @staticmethod
    def list_transactions_for_export(
        db: Session,
        company_id: int,
        branch_id: Optional[int] = None,
        operation_type: Optional[OperationType] = None,
        status: Optional[TransactionStatus] = None,
        performed_by: Optional[int] = None,
        item_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        search: Optional[str] = None,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> List[Transaction]:
        """
        List all transactions for export using the same filters/search/sort as listing.
        This method does not apply pagination.
        """
        query = db.query(Transaction).join(
            Branch, Transaction.branch_id == Branch.id
        ).filter(
            Branch.company_id == company_id
        )

        if branch_id is not None:
            query = query.filter(
                or_(
                    Transaction.branch_id == branch_id,
                    Transaction.destination_branch_id == branch_id
                )
            )

        if operation_type is not None:
            query = query.filter(Transaction.operation_type == operation_type)

        if status is not None:
            query = query.filter(Transaction.status == status)

        if performed_by is not None:
            query = query.join(TransactionEvent).filter(
                TransactionEvent.performed_by == performed_by
            )

        if item_id is not None:
            query = query.filter(
                Transaction.lines.any(TransactionLine.item_id == item_id)
            )

        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                Transaction.lines.any(
                    TransactionLine.item.has(
                        or_(
                            Item.name.ilike(search_pattern),
                            Item.sku.ilike(search_pattern)
                        )
                    )
                )
            )

        if start_date is not None:
            start_datetime = datetime.combine(start_date, time.min)
            query = query.filter(Transaction.created_at >= start_datetime)

        if end_date is not None:
            end_datetime = datetime.combine(end_date, time.max)
            query = query.filter(Transaction.created_at <= end_datetime)

        query = query.distinct()

        if order_by == "total_items":
            query = query.outerjoin(TransactionLine).group_by(Transaction.id)
            order_column = func.count(TransactionLine.id)
        else:
            order_column = Transaction.created_at

        if order_desc:
            query = query.order_by(order_column.desc() if order_by != "total_items" else desc(order_column))
        else:
            query = query.order_by(order_column.asc() if order_by != "total_items" else asc(order_column))

        return query.options(
            joinedload(Transaction.lines).joinedload(TransactionLine.item),
            joinedload(Transaction.events),
            joinedload(Transaction.branch),
            joinedload(Transaction.destination_branch)
        ).all()

    @staticmethod
    def get_by_id(db: Session, transaction_id: int) -> Optional[Transaction]:
        """Get transaction by ID with eager loading of related data"""
        return db.query(Transaction).filter(
            Transaction.id == transaction_id
        ).options(
            joinedload(Transaction.lines),
            joinedload(Transaction.events)
        ).first()

    @staticmethod
    def list_transactions(
        db: Session,
        company_id: int,
        page: int = 1,
        page_size: int = 20,
        branch_id: Optional[int] = None,
        operation_type: Optional[OperationType] = None,
        status: Optional[TransactionStatus] = None,
        performed_by: Optional[int] = None,
        item_id: Optional[int] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        search: Optional[str] = None,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> Tuple[List[Transaction], int]:
        """
        List transactions for a company with comprehensive filters.
        Returns tuple of (transactions, total_count)
        
        Filters:
        - company_id: Required, filter by company
        - branch_id: Optional, filter by branch as origin or as destination
        - operation_type: Optional, filter by operation type (IN, OUT, TRANSFER, ADJUSTMENT)
        - status: Optional, filter by status (PENDING, TRANSIT, CANCELLED, COMPLETED)
        - performed_by: Optional, filter by user who completed the transaction
        - item_id: Optional, filter by item (if transaction_line contains this item)
        - search: Optional, search in item names and SKUs
        
        Ordering:
        - order_by: "created_at" or "total_items"
        - order_desc: True for descending, False for ascending
        """
        # Base query: join with branch to filter by company
        query = db.query(Transaction).join(
            Branch, Transaction.branch_id == Branch.id
        ).filter(
            Branch.company_id == company_id
        )

        # Apply filters
        if branch_id is not None:
            # Filter by branch as origin or as destination
            query = query.filter(
                or_(
                    Transaction.branch_id == branch_id,
                    Transaction.destination_branch_id == branch_id
                )
            )
        
        if operation_type is not None:
            query = query.filter(Transaction.operation_type == operation_type)
        
        if status is not None:
            query = query.filter(Transaction.status == status)
        
        # Filter by user who performed action (check transaction_events)
        if performed_by is not None:
            query = query.join(TransactionEvent).filter(
                TransactionEvent.performed_by == performed_by
            )
        
        # Filter by item in transaction_lines
        if item_id is not None:
            query = query.filter(
                Transaction.lines.any(TransactionLine.item_id == item_id)
            )
        
        # Search by item name or SKU
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                Transaction.lines.any(
                    TransactionLine.item.has(
                        or_(
                            Item.name.ilike(search_pattern),
                            Item.sku.ilike(search_pattern)
                        )
                    )
                )
            )

        if start_date is not None:
            start_datetime = datetime.combine(start_date, time.min)
            query = query.filter(Transaction.created_at >= start_datetime)

        if end_date is not None:
            end_datetime = datetime.combine(end_date, time.max)
            query = query.filter(Transaction.created_at <= end_datetime)
        
        # Remove duplicates from joins
        query = query.distinct()

        # Get total count before pagination
        total_count = query.count()

        # Apply ordering
        if order_by == "total_items":
            # Count items per transaction and order by that
            query = query.outerjoin(TransactionLine).group_by(Transaction.id)
            order_column = func.count(TransactionLine.id)
        else:
            order_column = Transaction.created_at

        if order_desc:
            query = query.order_by(order_column.desc() if order_by != "total_items" else desc(order_column))
        else:
            query = query.order_by(order_column.asc() if order_by != "total_items" else asc(order_column))

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Execute with eager loading
        transactions = query.options(
            joinedload(Transaction.lines),
            joinedload(Transaction.events)
        ).all()

        return transactions, total_count

    @staticmethod
    def create(db: Session, transaction: Transaction) -> Transaction:
        """Create a new transaction"""
        db.add(transaction)
        db.flush()
        return transaction

    @staticmethod
    def create_line(db: Session, transaction_line: TransactionLine) -> TransactionLine:
        """Create a transaction line"""
        db.add(transaction_line)
        db.flush()
        return transaction_line

    @staticmethod
    def create_event(db: Session, event: TransactionEvent) -> TransactionEvent:
        """Create a transaction event for auditing"""
        db.add(event)
        db.flush()
        return event

    @staticmethod
    def update(db: Session, transaction: Transaction) -> Transaction:
        """Generic update for transaction"""
        db.flush()
        return transaction

    @staticmethod
    def delete(db: Session, transaction: Transaction) -> None:
        """Delete a transaction"""
        db.delete(transaction)
        db.flush()

    @staticmethod
    def commit(db: Session) -> None:
        """Commit changes to database"""
        db.commit()
