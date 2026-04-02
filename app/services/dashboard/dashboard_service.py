from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.datetime_utils import madrid_now
from app.db.models.item import Item
from app.db.models.transaction import OperationType, Transaction, TransactionStatus
from app.db.models.transaction_line import TransactionLine
from app.db.models.user import User
from app.repositories.branch_repository import BranchRepository
from app.repositories.item_repository import ItemRepository
from app.repositories.stock_movement_repository import StockMovementRepository
from app.schemas.dashboard import (
    DashboardBranchScope,
    DashboardActivityBranchMetrics,
    DashboardActivityResponse,
    DashboardStockAlertItem,
    DashboardStockBuckets,
    DashboardStockRiskBranchMetrics,
    DashboardStockRiskResponse,
    DashboardStaleTransaction,
)
from app.services.dashboard.dashboard_rules import (
    LineFlowDirection,
    classify_transaction_line_direction,
    days_since_last_event,
    is_stale_pending_or_transit,
)
from app.services.user.user_service import UserService


class DashboardService:
    """Business logic for dashboard KPI endpoints."""

    @staticmethod
    def _resolve_active_scope_branches(
        db: Session,
        current_user: User,
        branch_id: Optional[int],
    ) -> List:
        """Resolve active branches for the current dashboard request scope."""
        if branch_id is not None:
            branch = BranchRepository.get_by_id(db, branch_id)
            if not branch:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="BRANCH_NOT_FOUND",
                )

            if not branch.is_active:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="BRANCH_INACTIVE",
                )

            if branch.company_id != current_user.company_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="BRANCH_NOT_FOUND",
                )

            if current_user.branch_id is not None and current_user.branch_id != branch_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="BRANCH_ACCESS_DENIED",
                )

            return [branch]

        if current_user.branch_id is not None:
            branch = BranchRepository.get_by_id(db, current_user.branch_id)
            if not branch or not branch.is_active or branch.company_id != current_user.company_id:
                return []
            return [branch]

        return BranchRepository.get_by_company_id(
            db,
            current_user.company_id,
            is_active=True,
        )

    @staticmethod
    def _compute_stock_for_branch_items(
        items: List[Item],
        branch_id: int,
        stock_dict: dict,
    ) -> tuple[DashboardStockBuckets, List[DashboardStockAlertItem]]:
        """Compute stock buckets and alert items for one branch."""
        zero_count = 0
        low_count = 0
        healthy_count = 0
        alert_items: List[DashboardStockAlertItem] = []

        for item in items:
            stock = stock_dict.get((item.id, branch_id), Decimal("0.000"))

            if stock == 0:
                zero_count += 1
                alert_items.append(
                    DashboardStockAlertItem(
                        item_id=item.id,
                        item_name=item.name,
                        item_sku=item.sku,
                        stock=float(stock),
                        low_stock_threshold=item.low_stock_threshold,
                        stock_status="ZERO",
                    )
                )
                continue

            if stock < item.low_stock_threshold:
                low_count += 1
                alert_items.append(
                    DashboardStockAlertItem(
                        item_id=item.id,
                        item_name=item.name,
                        item_sku=item.sku,
                        stock=float(stock),
                        low_stock_threshold=item.low_stock_threshold,
                        stock_status="LOW",
                    )
                )
                continue

            healthy_count += 1

        return (
            DashboardStockBuckets(
                zero_stock_items=zero_count,
                low_stock_items=low_count,
                healthy_stock_items=healthy_count,
            ),
            alert_items,
        )

    @staticmethod
    def _list_stale_transactions_for_branch(
        db: Session,
        branch_id: int,
    ) -> List[DashboardStaleTransaction]:
        """Return stale pending/transit transactions for one branch."""
        now_dt = madrid_now()

        candidates = db.query(Transaction).filter(
            Transaction.status.in_([TransactionStatus.PENDING, TransactionStatus.TRANSIT]),
            (Transaction.branch_id == branch_id)
            | (Transaction.destination_branch_id == branch_id),
        ).all()

        stale_transactions: List[DashboardStaleTransaction] = []

        for tx in candidates:
            last_event = tx.last_event_at or tx.created_at
            if not is_stale_pending_or_transit(last_event, now_dt):
                continue

            stale_transactions.append(
                DashboardStaleTransaction(
                    transaction_id=tx.id,
                    operation_type=tx.operation_type.value,
                    status=tx.status.value,
                    last_event_at=last_event,
                    days_since_last_event=days_since_last_event(last_event, now_dt),
                    origin_branch_id=tx.branch_id,
                    destination_branch_id=tx.destination_branch_id,
                )
            )

        stale_transactions.sort(key=lambda tx: tx.days_since_last_event, reverse=True)
        return stale_transactions

    @staticmethod
    def get_stock_risk_metrics(
        db: Session,
        current_user: User,
        branch_id: Optional[int] = None,
    ) -> DashboardStockRiskResponse:
        """
        Return dashboard stock-risk metrics by active branch scope.

        Includes:
        - Pending and transit operations count
        - Stock buckets (zero / low / healthy)
        - Low and zero stock item list
        - Stale pending/transit transaction list
        """
        UserService.validate_user_active(current_user)

        branches = DashboardService._resolve_active_scope_branches(
            db=db,
            current_user=current_user,
            branch_id=branch_id,
        )

        items = ItemRepository.get_by_company_id(db, current_user.company_id)
        active_items = [item for item in items if item.is_active]

        branch_ids = [branch.id for branch in branches]
        item_ids = [item.id for item in active_items]
        stock_dict = StockMovementRepository.get_stock_by_items_and_branches(
            db,
            item_ids,
            branch_ids,
        )

        response_data: List[DashboardStockRiskBranchMetrics] = []

        for branch in branches:
            pending_count = db.query(Transaction).filter(
                Transaction.status.in_([TransactionStatus.PENDING, TransactionStatus.TRANSIT]),
                (Transaction.branch_id == branch.id)
                | (Transaction.destination_branch_id == branch.id),
            ).count()

            stock_buckets, alert_items = DashboardService._compute_stock_for_branch_items(
                items=active_items,
                branch_id=branch.id,
                stock_dict=stock_dict,
            )

            stale_transactions = DashboardService._list_stale_transactions_for_branch(
                db=db,
                branch_id=branch.id,
            )

            response_data.append(
                DashboardStockRiskBranchMetrics(
                    branch=DashboardBranchScope(
                        branch_id=branch.id,
                        branch_name=branch.name,
                    ),
                    pending_operations_count=pending_count,
                    stock_buckets=stock_buckets,
                    stock_alert_items=alert_items,
                    stale_transactions=stale_transactions,
                )
            )

        return DashboardStockRiskResponse(data=response_data)

    @staticmethod
    def _get_transaction_reference_datetime(transaction: Transaction) -> datetime:
        """Use last_event_at when available, otherwise fallback to created_at."""
        return transaction.last_event_at or transaction.created_at

    @staticmethod
    def _get_activity_period_start(period: str, now_dt: datetime) -> Optional[datetime]:
        """Return the inclusive start datetime for the requested activity period."""
        current_date = now_dt.date()

        if period == "day":
            return datetime.combine(current_date, datetime.min.time())

        if period == "week":
            week_start = current_date - timedelta(days=current_date.weekday())
            return datetime.combine(week_start, datetime.min.time())

        if period == "month":
            month_start = date(current_date.year, current_date.month, 1)
            return datetime.combine(month_start, datetime.min.time())

        if period == "total":
            return None

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INVALID_ACTIVITY_PERIOD",
        )

    @staticmethod
    def _is_transaction_in_period(
        transaction: Transaction,
        now_dt: datetime,
        period: str,
    ) -> bool:
        """Check whether transaction belongs to the requested activity window."""
        start_dt = DashboardService._get_activity_period_start(period, now_dt)
        if start_dt is None:
            return True

        reference_dt = DashboardService._get_transaction_reference_datetime(transaction)
        return start_dt <= reference_dt <= now_dt

    @staticmethod
    def _count_branch_line_flows(
        transaction_lines: List[TransactionLine],
        transaction: Transaction,
        target_branch_id: int,
    ) -> tuple[int, int, dict[str, int], dict[str, int]]:
        """Count incoming and outgoing lines plus operation-type breakdowns."""
        incoming_count = 0
        outgoing_count = 0
        incoming_by_operation = {
            OperationType.IN.value: 0,
            OperationType.OUT.value: 0,
            OperationType.TRANSFER.value: 0,
            OperationType.ADJUSTMENT.value: 0,
        }
        outgoing_by_operation = {
            OperationType.IN.value: 0,
            OperationType.OUT.value: 0,
            OperationType.TRANSFER.value: 0,
            OperationType.ADJUSTMENT.value: 0,
        }

        for line in transaction_lines:
            direction = classify_transaction_line_direction(
                operation_type=transaction.operation_type,
                quantity=float(line.quantity),
                origin_branch_id=transaction.branch_id,
                destination_branch_id=transaction.destination_branch_id,
                target_branch_id=target_branch_id,
            )

            if direction == LineFlowDirection.INCOMING:
                incoming_count += 1
                incoming_by_operation[transaction.operation_type.value] += 1
            elif direction == LineFlowDirection.OUTGOING:
                outgoing_count += 1
                outgoing_by_operation[transaction.operation_type.value] += 1

        return incoming_count, outgoing_count, incoming_by_operation, outgoing_by_operation

    @staticmethod
    def get_activity_metrics(
        db: Session,
        current_user: User,
        branch_id: Optional[int] = None,
        period: str = "day",
    ) -> DashboardActivityResponse:
        """
        Return dashboard activity metrics by active branch scope.

        Includes:
        - Operations count (status COMPLETED only)
        - Incoming transaction lines count (status COMPLETED only)
        - Outgoing transaction lines count (status COMPLETED only)
        - Incoming/outgoing transaction line breakdown by operation type
        """
        UserService.validate_user_active(current_user)

        branches = DashboardService._resolve_active_scope_branches(
            db=db,
            current_user=current_user,
            branch_id=branch_id,
        )

        now_dt = madrid_now()
        response_data: List[DashboardActivityBranchMetrics] = []

        for branch in branches:
            transactions = db.query(Transaction).options(
                joinedload(Transaction.lines)
            ).filter(
                Transaction.status == TransactionStatus.COMPLETED,
                (Transaction.branch_id == branch.id)
                | (Transaction.destination_branch_id == branch.id)
            ).all()

            operations_count = 0
            incoming_lines_count = 0
            outgoing_lines_count = 0
            incoming_by_operation = {
                OperationType.IN.value: 0,
                OperationType.OUT.value: 0,
                OperationType.TRANSFER.value: 0,
                OperationType.ADJUSTMENT.value: 0,
            }
            outgoing_by_operation = {
                OperationType.IN.value: 0,
                OperationType.OUT.value: 0,
                OperationType.TRANSFER.value: 0,
                OperationType.ADJUSTMENT.value: 0,
            }

            for transaction in transactions:
                if not DashboardService._is_transaction_in_period(transaction, now_dt, period):
                    continue

                operations_count += 1
                incoming_increment, outgoing_increment, incoming_breakdown, outgoing_breakdown = DashboardService._count_branch_line_flows(
                    transaction_lines=transaction.lines,
                    transaction=transaction,
                    target_branch_id=branch.id,
                )
                incoming_lines_count += incoming_increment
                outgoing_lines_count += outgoing_increment
                for operation_type in incoming_by_operation:
                    incoming_by_operation[operation_type] += incoming_breakdown[operation_type]
                    outgoing_by_operation[operation_type] += outgoing_breakdown[operation_type]

            response_data.append(
                DashboardActivityBranchMetrics(
                    branch=DashboardBranchScope(
                        branch_id=branch.id,
                        branch_name=branch.name,
                    ),
                    operations_count=operations_count,
                    incoming_transaction_lines_count=incoming_lines_count,
                    outgoing_transaction_lines_count=outgoing_lines_count,
                    incoming_transaction_lines_by_operation=incoming_by_operation,
                    outgoing_transaction_lines_by_operation=outgoing_by_operation,
                )
            )

        return DashboardActivityResponse(
            period=period,
            data=response_data,
        )
