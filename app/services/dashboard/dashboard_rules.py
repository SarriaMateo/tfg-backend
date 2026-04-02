from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from app.db.models.transaction import OperationType


class LineFlowDirection(str, Enum):
    INCOMING = "INCOMING"
    OUTGOING = "OUTGOING"
    NEUTRAL = "NEUTRAL"


def classify_transaction_line_direction(
    operation_type: OperationType,
    quantity: float,
    origin_branch_id: int,
    destination_branch_id: Optional[int],
    target_branch_id: int,
) -> LineFlowDirection:
    """Classify a transaction line direction for one target branch."""
    if operation_type == OperationType.IN:
        return LineFlowDirection.INCOMING

    if operation_type == OperationType.OUT:
        return LineFlowDirection.OUTGOING

    if operation_type == OperationType.TRANSFER:
        if target_branch_id == origin_branch_id:
            return LineFlowDirection.OUTGOING
        if destination_branch_id is not None and target_branch_id == destination_branch_id:
            return LineFlowDirection.INCOMING
        return LineFlowDirection.NEUTRAL

    if operation_type == OperationType.ADJUSTMENT:
        if quantity > 0:
            return LineFlowDirection.INCOMING
        if quantity < 0:
            return LineFlowDirection.OUTGOING
        return LineFlowDirection.NEUTRAL

    return LineFlowDirection.NEUTRAL


def days_since_last_event(last_event_at: datetime, now_dt: datetime) -> int:
    """Return full natural day difference between now and last event date."""
    return (now_dt.date() - last_event_at.date()).days


def elapsed_days_excluding_sundays(last_event_at: datetime, now_dt: datetime) -> int:
    """Count elapsed calendar days excluding Sundays."""
    start_date = last_event_at.date()
    end_date = now_dt.date()

    if end_date <= start_date:
        return 0

    elapsed = 0
    current = start_date + timedelta(days=1)

    while current <= end_date:
        if current.weekday() != 6:  # Sunday is 6
            elapsed += 1
        current += timedelta(days=1)

    return elapsed


def is_stale_pending_or_transit(last_event_at: datetime, now_dt: datetime) -> bool:
    """
    Determine stale status using natural-day cutoff with Sunday exception.

    Rule implemented:
    - Include from Wednesday when last event was Monday.
    - Include from Tuesday when last event was Saturday.
    """
    return elapsed_days_excluding_sundays(last_event_at, now_dt) >= 2
