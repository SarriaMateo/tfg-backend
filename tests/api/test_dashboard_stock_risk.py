from datetime import datetime
from decimal import Decimal

import pytest

from app.core.security import create_access_token, hash_password
from app.db.models.branch import Branch
from app.db.models.company import Company
from app.db.models.item import Item, Unit
from app.db.models.stock_movement import MovementType, StockMovement
from app.db.models.transaction import OperationType, Transaction, TransactionStatus
from app.db.models.user import Role, User


@pytest.fixture
def dashboard_stock_risk_data(db_session):
    company = Company(name="Dash Co", email="dash@co.com", nif="12345678A")
    db_session.add(company)
    db_session.flush()

    branch_a = Branch(name="Sede A", address="Dir A", company_id=company.id, is_active=True)
    branch_b = Branch(name="Sede B", address="Dir B", company_id=company.id, is_active=True)
    branch_inactive = Branch(
        name="Sede Inactiva",
        address="Dir C",
        company_id=company.id,
        is_active=False,
    )
    db_session.add_all([branch_a, branch_b, branch_inactive])
    db_session.flush()

    admin_user = User(
        name="Admin",
        username="dash_admin",
        hashed_password=hash_password("password123"),
        role=Role.ADMIN,
        is_active=True,
        company_id=company.id,
        branch_id=None,
    )
    employee_a = User(
        name="Empleado A",
        username="dash_emp_a",
        hashed_password=hash_password("password123"),
        role=Role.EMPLOYEE,
        is_active=True,
        company_id=company.id,
        branch_id=branch_a.id,
    )
    db_session.add_all([admin_user, employee_a])
    db_session.flush()

    item_zero = Item(
        name="Item Zero",
        sku="IZERO001",
        unit=Unit.UNIT,
        is_active=True,
        low_stock_threshold=5,
        company_id=company.id,
    )
    item_low = Item(
        name="Item Low",
        sku="ILOW0001",
        unit=Unit.UNIT,
        is_active=True,
        low_stock_threshold=10,
        company_id=company.id,
    )
    item_equal_threshold = Item(
        name="Item Equal",
        sku="IEQ00001",
        unit=Unit.UNIT,
        is_active=True,
        low_stock_threshold=7,
        company_id=company.id,
    )
    item_high = Item(
        name="Item High",
        sku="IHIGH001",
        unit=Unit.UNIT,
        is_active=True,
        low_stock_threshold=3,
        company_id=company.id,
    )
    db_session.add_all([item_zero, item_low, item_equal_threshold, item_high])
    db_session.flush()

    base_tx = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.COMPLETED,
        created_at=datetime(2026, 4, 1, 10, 0, 0),
        last_event_at=datetime(2026, 4, 1, 10, 0, 0),
        branch_id=branch_a.id,
    )
    db_session.add(base_tx)
    db_session.flush()

    db_session.add_all(
        [
            StockMovement(
                quantity=Decimal("3.000"),
                movement_type=MovementType.IN,
                created_at=datetime(2026, 4, 1, 10, 0, 0),
                item_id=item_low.id,
                branch_id=branch_a.id,
                transaction_id=base_tx.id,
            ),
            StockMovement(
                quantity=Decimal("7.000"),
                movement_type=MovementType.IN,
                created_at=datetime(2026, 4, 1, 10, 0, 0),
                item_id=item_equal_threshold.id,
                branch_id=branch_a.id,
                transaction_id=base_tx.id,
            ),
            StockMovement(
                quantity=Decimal("9.000"),
                movement_type=MovementType.IN,
                created_at=datetime(2026, 4, 1, 10, 0, 0),
                item_id=item_high.id,
                branch_id=branch_a.id,
                transaction_id=base_tx.id,
            ),
        ]
    )

    pending_tx = Transaction(
        operation_type=OperationType.OUT,
        status=TransactionStatus.PENDING,
        created_at=datetime(2026, 4, 7, 10, 0, 0),
        last_event_at=datetime(2026, 4, 7, 10, 0, 0),
        branch_id=branch_a.id,
    )
    stale_tx_monday = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.PENDING,
        created_at=datetime(2026, 4, 6, 9, 0, 0),
        last_event_at=datetime(2026, 4, 6, 9, 0, 0),
        branch_id=branch_a.id,
    )
    stale_tx_saturday = Transaction(
        operation_type=OperationType.TRANSFER,
        status=TransactionStatus.TRANSIT,
        created_at=datetime(2026, 4, 4, 9, 0, 0),
        last_event_at=datetime(2026, 4, 4, 9, 0, 0),
        branch_id=branch_a.id,
        destination_branch_id=branch_b.id,
    )
    fresh_transit_tx = Transaction(
        operation_type=OperationType.TRANSFER,
        status=TransactionStatus.TRANSIT,
        created_at=datetime(2026, 4, 8, 8, 0, 0),
        last_event_at=datetime(2026, 4, 8, 8, 0, 0),
        branch_id=branch_a.id,
        destination_branch_id=branch_b.id,
    )
    db_session.add_all([pending_tx, stale_tx_monday, stale_tx_saturday, fresh_transit_tx])
    db_session.commit()

    return {
        "company": company,
        "branch_a": branch_a,
        "branch_b": branch_b,
        "branch_inactive": branch_inactive,
        "admin_user": admin_user,
        "employee_a": employee_a,
        "stale_tx_monday": stale_tx_monday,
        "stale_tx_saturday": stale_tx_saturday,
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
async def test_dashboard_stock_risk_branch_scope_counts(client, dashboard_stock_risk_data, monkeypatch):
    monkeypatch.setattr(
        "app.services.dashboard.dashboard_service.madrid_now",
        lambda: datetime(2026, 4, 8, 10, 0, 0),
    )

    token = _token_for_user(dashboard_stock_risk_data["admin_user"])
    branch_a_id = dashboard_stock_risk_data["branch_a"].id

    response = await client.get(
        f"/api/v1/dashboard/stock-risk?branch_id={branch_a_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["data"]) == 1

    branch_data = payload["data"][0]
    assert branch_data["pending_operations_count"] == 4
    assert branch_data["stock_buckets"] == {
        "zero_stock_items": 1,
        "low_stock_items": 1,
        "healthy_stock_items": 2,
    }

    stock_statuses = {item["stock_status"] for item in branch_data["stock_alert_items"]}
    assert stock_statuses == {"ZERO", "LOW"}

    stale_ids = {tx["transaction_id"] for tx in branch_data["stale_transactions"]}
    assert dashboard_stock_risk_data["stale_tx_monday"].id in stale_ids
    assert dashboard_stock_risk_data["stale_tx_saturday"].id in stale_ids
    assert all("days_since_last_event" in tx for tx in branch_data["stale_transactions"])


@pytest.mark.asyncio
async def test_dashboard_stock_risk_without_branch_returns_only_active_branches(
    client,
    dashboard_stock_risk_data,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.dashboard.dashboard_service.madrid_now",
        lambda: datetime(2026, 4, 8, 10, 0, 0),
    )

    token = _token_for_user(dashboard_stock_risk_data["admin_user"])

    response = await client.get(
        "/api/v1/dashboard/stock-risk",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    branch_ids = {entry["branch"]["branch_id"] for entry in payload["data"]}

    assert dashboard_stock_risk_data["branch_a"].id in branch_ids
    assert dashboard_stock_risk_data["branch_b"].id in branch_ids
    assert dashboard_stock_risk_data["branch_inactive"].id not in branch_ids


@pytest.mark.asyncio
async def test_dashboard_stock_risk_employee_cannot_request_other_branch(
    client,
    dashboard_stock_risk_data,
):
    token = _token_for_user(dashboard_stock_risk_data["employee_a"])
    branch_b_id = dashboard_stock_risk_data["branch_b"].id

    response = await client.get(
        f"/api/v1/dashboard/stock-risk?branch_id={branch_b_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "BRANCH_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_dashboard_stock_risk_inactive_branch_filter_returns_error(
    client,
    dashboard_stock_risk_data,
):
    token = _token_for_user(dashboard_stock_risk_data["admin_user"])
    inactive_branch_id = dashboard_stock_risk_data["branch_inactive"].id

    response = await client.get(
        f"/api/v1/dashboard/stock-risk?branch_id={inactive_branch_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "BRANCH_INACTIVE"
