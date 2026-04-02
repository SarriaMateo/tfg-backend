from datetime import datetime
from decimal import Decimal

import pytest

from app.core.security import create_access_token, hash_password
from app.db.models.branch import Branch
from app.db.models.company import Company
from app.db.models.item import Item, Unit
from app.db.models.transaction import OperationType, Transaction, TransactionStatus
from app.db.models.transaction_line import TransactionLine
from app.db.models.user import Role, User


@pytest.fixture
def dashboard_activity_data(db_session):
    company = Company(name="Dash Activity Co", email="dash-activity@co.com", nif="11223344A")
    db_session.add(company)
    db_session.flush()

    branch_a = Branch(name="Sede A", address="Dir A", company_id=company.id, is_active=True)
    branch_b = Branch(name="Sede B", address="Dir B", company_id=company.id, is_active=True)
    branch_inactive = Branch(name="Sede Inactiva", address="Dir C", company_id=company.id, is_active=False)
    db_session.add_all([branch_a, branch_b, branch_inactive])
    db_session.flush()

    admin_user = User(
        name="Admin Activity",
        username="dash_activity_admin",
        hashed_password=hash_password("password123"),
        role=Role.ADMIN,
        is_active=True,
        company_id=company.id,
        branch_id=None,
    )
    employee_a = User(
        name="Empleado A",
        username="dash_activity_emp_a",
        hashed_password=hash_password("password123"),
        role=Role.EMPLOYEE,
        is_active=True,
        company_id=company.id,
        branch_id=branch_a.id,
    )
    db_session.add_all([admin_user, employee_a])
    db_session.flush()

    item_1 = Item(
        name="Item 1",
        sku="IACT0011",
        unit=Unit.UNIT,
        is_active=True,
        low_stock_threshold=5,
        company_id=company.id,
    )
    item_2 = Item(
        name="Item 2",
        sku="IACT0022",
        unit=Unit.UNIT,
        is_active=True,
        low_stock_threshold=5,
        company_id=company.id,
    )
    db_session.add_all([item_1, item_2])
    db_session.flush()

    def add_tx(
        operation_type,
        branch_id,
        destination_branch_id,
        status,
        last_event_at,
        quantities,
        items,
    ):
        tx = Transaction(
            operation_type=operation_type,
            status=status,
            created_at=last_event_at,
            last_event_at=last_event_at,
            branch_id=branch_id,
            destination_branch_id=destination_branch_id,
        )
        db_session.add(tx)
        db_session.flush()

        for qty, item in zip(quantities, items):
            db_session.add(
                TransactionLine(
                    quantity=Decimal(qty),
                    item_id=item.id,
                    transaction_id=tx.id,
                )
            )

        return tx

    # Recent activity for 2026-04-10 day window.
    add_tx(OperationType.IN, branch_a.id, None, TransactionStatus.COMPLETED, datetime(2026, 4, 10, 9, 0, 0), ["5.000"], [item_1])
    add_tx(OperationType.OUT, branch_a.id, None, TransactionStatus.COMPLETED, datetime(2026, 4, 10, 9, 5, 0), ["2.000"], [item_1])
    add_tx(OperationType.TRANSFER, branch_a.id, branch_b.id, TransactionStatus.TRANSIT, datetime(2026, 4, 10, 9, 10, 0), ["4.000"], [item_2])
    add_tx(OperationType.ADJUSTMENT, branch_a.id, None, TransactionStatus.COMPLETED, datetime(2026, 4, 10, 9, 15, 0), ["3.000"], [item_1])
    add_tx(OperationType.ADJUSTMENT, branch_a.id, None, TransactionStatus.COMPLETED, datetime(2026, 4, 10, 9, 20, 0), ["-1.000"], [item_1])
    add_tx(OperationType.OUT, branch_b.id, None, TransactionStatus.COMPLETED, datetime(2026, 4, 10, 9, 25, 0), ["1.000"], [item_2])

    # Historical operation outside 3-day window.
    add_tx(OperationType.IN, branch_a.id, None, TransactionStatus.COMPLETED, datetime(2026, 4, 1, 10, 0, 0), ["9.000"], [item_1])

    # Historical operation outside the month window.
    add_tx(OperationType.OUT, branch_a.id, None, TransactionStatus.COMPLETED, datetime(2026, 3, 31, 10, 0, 0), ["1.000"], [item_1])

    db_session.commit()

    return {
        "branch_a": branch_a,
        "branch_b": branch_b,
        "branch_inactive": branch_inactive,
        "admin_user": admin_user,
        "employee_a": employee_a,
    }


def _token_for_user(user: User) -> str:
    return create_access_token(
        {
            "sub": user.username,
            "user_id": user.id,
            "role": user.role.value,
            "company_id": user.company_id,
            "branch_id": user.branch_id,
        }
    )


@pytest.mark.asyncio
async def test_dashboard_activity_branch_day_default_counts(client, dashboard_activity_data, monkeypatch):
    monkeypatch.setattr(
        "app.services.dashboard.dashboard_service.madrid_now",
        lambda: datetime(2026, 4, 10, 12, 0, 0),
    )

    token = _token_for_user(dashboard_activity_data["admin_user"])
    branch_a_id = dashboard_activity_data["branch_a"].id

    response = await client.get(
        f"/api/v1/dashboard/activity?branch_id={branch_a_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["period"] == "day"
    assert len(payload["data"]) == 1

    metrics = payload["data"][0]
    assert metrics["operations_count"] == 4
    assert metrics["incoming_transaction_lines_count"] == 2
    assert metrics["outgoing_transaction_lines_count"] == 2
    assert metrics["incoming_transaction_lines_by_operation"] == {
        "IN": 1,
        "OUT": 0,
        "TRANSFER": 0,
        "ADJUSTMENT": 1,
    }
    assert metrics["outgoing_transaction_lines_by_operation"] == {
        "IN": 0,
        "OUT": 1,
        "TRANSFER": 0,
        "ADJUSTMENT": 1,
    }


@pytest.mark.asyncio
async def test_dashboard_activity_week_counts(client, dashboard_activity_data, monkeypatch):
    monkeypatch.setattr(
        "app.services.dashboard.dashboard_service.madrid_now",
        lambda: datetime(2026, 4, 10, 12, 0, 0),
    )

    token = _token_for_user(dashboard_activity_data["admin_user"])
    branch_a_id = dashboard_activity_data["branch_a"].id

    response = await client.get(
        f"/api/v1/dashboard/activity?branch_id={branch_a_id}&period=week",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    metrics = response.json()["data"][0]

    assert response.json()["period"] == "week"
    assert metrics["operations_count"] == 4
    assert metrics["incoming_transaction_lines_count"] == 2
    assert metrics["outgoing_transaction_lines_count"] == 2


@pytest.mark.asyncio
async def test_dashboard_activity_month_counts_exclude_previous_month(
    client,
    dashboard_activity_data,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.dashboard.dashboard_service.madrid_now",
        lambda: datetime(2026, 4, 10, 12, 0, 0),
    )

    token = _token_for_user(dashboard_activity_data["admin_user"])
    branch_a_id = dashboard_activity_data["branch_a"].id

    response = await client.get(
        f"/api/v1/dashboard/activity?branch_id={branch_a_id}&period=month",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    metrics = response.json()["data"][0]

    assert response.json()["period"] == "month"
    assert metrics["operations_count"] == 5
    assert metrics["incoming_transaction_lines_count"] == 3
    assert metrics["outgoing_transaction_lines_count"] == 2


@pytest.mark.asyncio
async def test_dashboard_activity_total_includes_historical_operations(
    client,
    dashboard_activity_data,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.dashboard.dashboard_service.madrid_now",
        lambda: datetime(2026, 4, 10, 12, 0, 0),
    )

    token = _token_for_user(dashboard_activity_data["admin_user"])
    branch_a_id = dashboard_activity_data["branch_a"].id

    response = await client.get(
        f"/api/v1/dashboard/activity?branch_id={branch_a_id}&period=total",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    metrics = response.json()["data"][0]

    assert response.json()["period"] == "total"
    assert metrics["operations_count"] == 6
    assert metrics["incoming_transaction_lines_count"] == 3
    assert metrics["outgoing_transaction_lines_count"] == 3


@pytest.mark.asyncio
async def test_dashboard_activity_without_branch_returns_active_branches_only(
    client,
    dashboard_activity_data,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.dashboard.dashboard_service.madrid_now",
        lambda: datetime(2026, 4, 10, 12, 0, 0),
    )

    token = _token_for_user(dashboard_activity_data["admin_user"])
    response = await client.get(
        "/api/v1/dashboard/activity?period=week",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    branch_ids = {entry["branch"]["branch_id"] for entry in response.json()["data"]}

    assert dashboard_activity_data["branch_a"].id in branch_ids
    assert dashboard_activity_data["branch_b"].id in branch_ids
    assert dashboard_activity_data["branch_inactive"].id not in branch_ids


@pytest.mark.asyncio
async def test_dashboard_activity_employee_cannot_query_other_branch(client, dashboard_activity_data):
    token = _token_for_user(dashboard_activity_data["employee_a"])
    branch_b_id = dashboard_activity_data["branch_b"].id

    response = await client.get(
        f"/api/v1/dashboard/activity?branch_id={branch_b_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "BRANCH_ACCESS_DENIED"
