from datetime import datetime

from app.db.models.transaction import OperationType
from app.services.dashboard.dashboard_rules import (
    LineFlowDirection,
    classify_transaction_line_direction,
    days_since_last_event,
    elapsed_days_excluding_sundays,
    is_stale_pending_or_transit,
)


def test_classify_in_line_as_incoming():
    direction = classify_transaction_line_direction(
        operation_type=OperationType.IN,
        quantity=5,
        origin_branch_id=1,
        destination_branch_id=None,
        target_branch_id=1,
    )

    assert direction == LineFlowDirection.INCOMING


def test_classify_out_line_as_outgoing():
    direction = classify_transaction_line_direction(
        operation_type=OperationType.OUT,
        quantity=5,
        origin_branch_id=1,
        destination_branch_id=None,
        target_branch_id=1,
    )

    assert direction == LineFlowDirection.OUTGOING


def test_classify_transfer_from_origin_as_outgoing():
    direction = classify_transaction_line_direction(
        operation_type=OperationType.TRANSFER,
        quantity=5,
        origin_branch_id=1,
        destination_branch_id=2,
        target_branch_id=1,
    )

    assert direction == LineFlowDirection.OUTGOING


def test_classify_transfer_for_destination_as_incoming():
    direction = classify_transaction_line_direction(
        operation_type=OperationType.TRANSFER,
        quantity=5,
        origin_branch_id=1,
        destination_branch_id=2,
        target_branch_id=2,
    )

    assert direction == LineFlowDirection.INCOMING


def test_classify_transfer_unrelated_branch_as_neutral():
    direction = classify_transaction_line_direction(
        operation_type=OperationType.TRANSFER,
        quantity=5,
        origin_branch_id=1,
        destination_branch_id=2,
        target_branch_id=3,
    )

    assert direction == LineFlowDirection.NEUTRAL


def test_classify_adjustment_positive_as_incoming():
    direction = classify_transaction_line_direction(
        operation_type=OperationType.ADJUSTMENT,
        quantity=3,
        origin_branch_id=1,
        destination_branch_id=None,
        target_branch_id=1,
    )

    assert direction == LineFlowDirection.INCOMING


def test_classify_adjustment_negative_as_outgoing():
    direction = classify_transaction_line_direction(
        operation_type=OperationType.ADJUSTMENT,
        quantity=-3,
        origin_branch_id=1,
        destination_branch_id=None,
        target_branch_id=1,
    )

    assert direction == LineFlowDirection.OUTGOING


def test_classify_adjustment_zero_as_neutral():
    direction = classify_transaction_line_direction(
        operation_type=OperationType.ADJUSTMENT,
        quantity=0,
        origin_branch_id=1,
        destination_branch_id=None,
        target_branch_id=1,
    )

    assert direction == LineFlowDirection.NEUTRAL


def test_days_since_last_event_uses_natural_day_delta():
    last_event_at = datetime(2026, 4, 6, 23, 59)  # Monday
    now_dt = datetime(2026, 4, 8, 0, 1)  # Wednesday

    assert days_since_last_event(last_event_at, now_dt) == 2


def test_elapsed_days_excluding_sundays_counts_weekdays_only():
    last_event_at = datetime(2026, 4, 4, 10, 0)  # Saturday
    now_dt = datetime(2026, 4, 7, 9, 0)  # Tuesday

    # Sunday is excluded, so counted days are Monday and Tuesday.
    assert elapsed_days_excluding_sundays(last_event_at, now_dt) == 2


def test_stale_rule_monday_included_from_wednesday():
    monday_event = datetime(2026, 4, 6, 10, 0)
    tuesday = datetime(2026, 4, 7, 8, 0)
    wednesday = datetime(2026, 4, 8, 8, 0)

    assert is_stale_pending_or_transit(monday_event, tuesday) is False
    assert is_stale_pending_or_transit(monday_event, wednesday) is True


def test_stale_rule_saturday_included_from_tuesday():
    saturday_event = datetime(2026, 4, 4, 10, 0)
    monday = datetime(2026, 4, 6, 8, 0)
    tuesday = datetime(2026, 4, 7, 8, 0)

    assert is_stale_pending_or_transit(saturday_event, monday) is False
    assert is_stale_pending_or_transit(saturday_event, tuesday) is True
