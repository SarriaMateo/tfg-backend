import pytest
from datetime import datetime, timedelta
from decimal import Decimal
import csv
import io

from app.core.security import create_access_token, hash_password
from app.db.models.branch import Branch
from app.db.models.company import Company
from app.db.models.item import Item, Unit
from app.db.models.transaction import OperationType, Transaction, TransactionStatus
from app.db.models.transaction_line import TransactionLine
from app.db.models.transaction_event import TransactionEvent, ActionType
from app.db.models.user import Role, User


@pytest.fixture
def export_contract_data(db_session):
    company = Company(
        name="Export Company",
        email="export@company.com",
        nif="12345678B",
    )
    db_session.add(company)
    db_session.flush()

    branch_a = Branch(name="Sede A", address="Calle A", company_id=company.id, is_active=True)
    branch_b = Branch(name="Sede B", address="Calle B", company_id=company.id, is_active=True)
    db_session.add_all([branch_a, branch_b])
    db_session.flush()

    item = Item(
        name="Articulo Export",
        sku="EXP-001",
        unit=Unit.UNIT,
        is_active=True,
        company_id=company.id,
    )
    item_kg = Item(
        name="Harina Export",
        sku="EXP-002",
        unit=Unit.KILOGRAM,
        is_active=True,
        company_id=company.id,
    )
    db_session.add_all([item, item_kg])
    db_session.flush()

    now = datetime.utcnow()

    admin = User(
        name="Admin Export",
        username="admin_export",
        hashed_password=hash_password("password123"),
        role=Role.ADMIN,
        is_active=True,
        company_id=company.id,
        branch_id=None,
    )
    manager_branch_a = User(
        name="Manager Export",
        username="manager_export",
        hashed_password=hash_password("password123"),
        role=Role.MANAGER,
        is_active=True,
        company_id=company.id,
        branch_id=branch_a.id,
    )
    employee = User(
        name="Employee Export",
        username="employee_export",
        hashed_password=hash_password("password123"),
        role=Role.EMPLOYEE,
        is_active=True,
        company_id=company.id,
        branch_id=None,
    )
    db_session.add_all([admin, manager_branch_a, employee])
    db_session.flush()

    transaction_branch_a = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.PENDING,
        created_at=now - timedelta(days=2),
        description="Entrada sede A",
        branch_id=branch_a.id,
    )
    transaction_branch_b = Transaction(
        operation_type=OperationType.OUT,
        status=TransactionStatus.PENDING,
        created_at=now - timedelta(days=1),
        description="Salida sede B",
        branch_id=branch_b.id,
    )
    transaction_to_branch_a = Transaction(
        operation_type=OperationType.TRANSFER,
        status=TransactionStatus.TRANSIT,
        created_at=now,
        description="Traspaso hacia sede A",
        branch_id=branch_b.id,
        destination_branch_id=branch_a.id,
    )
    db_session.add_all([transaction_branch_a, transaction_branch_b, transaction_to_branch_a])
    db_session.flush()

    db_session.add_all(
        [
            TransactionEvent(
                action_type=ActionType.CREATED,
                timestamp=now - timedelta(days=2),
                transaction_id=transaction_branch_a.id,
                performed_by=admin.id,
            ),
            TransactionEvent(
                action_type=ActionType.CREATED,
                timestamp=now - timedelta(days=1),
                transaction_id=transaction_branch_b.id,
                performed_by=admin.id,
            ),
            TransactionEvent(
                action_type=ActionType.CREATED,
                timestamp=now,
                transaction_id=transaction_to_branch_a.id,
                performed_by=manager_branch_a.id,
            ),
        ]
    )

    db_session.add_all(
        [
            TransactionLine(quantity=Decimal("1.000"), item_id=item.id, transaction_id=transaction_branch_a.id),
            TransactionLine(quantity=Decimal("2.000"), item_id=item.id, transaction_id=transaction_branch_b.id),
            TransactionLine(quantity=Decimal("3.000"), item_id=item.id, transaction_id=transaction_to_branch_a.id),
            TransactionLine(quantity=Decimal("5.500"), item_id=item_kg.id, transaction_id=transaction_to_branch_a.id),
        ]
    )
    db_session.commit()

    return {
        "users": {
            "admin": admin,
            "manager": manager_branch_a,
            "employee": employee,
        },
        "branches": {
            "a": branch_a,
            "b": branch_b,
        },
        "transactions": {
            "a": transaction_branch_a,
            "b": transaction_branch_b,
            "to_a": transaction_to_branch_a,
        },
    }


def _token_for(user: User) -> str:
    return create_access_token(
        {
            "sub": user.username,
            "user_id": user.id,
            "role": user.role.value,
            "company_id": user.company_id,
            "branch_id": user.branch_id,
        }
    )


def _read_csv(response) -> list[dict[str, str]]:
    text = response.content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    return list(reader)


def _dates_for_fixture() -> tuple[str, str]:
    now = datetime.utcnow()
    return (
        (now - timedelta(days=1, hours=1)).date().isoformat(),
        now.date().isoformat(),
    )


@pytest.mark.asyncio
async def test_export_contract_allows_admin(client, export_contract_data):
    admin = export_contract_data["users"]["admin"]
    token = _token_for(admin)

    response = await client.get(
        "/api/v1/transactions/export?format=csv",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=\"operaciones_" in response.headers["content-disposition"]
    rows = _read_csv(response)
    # Three transactions and one of them has two lines -> four CSV rows.
    assert len(rows) == 4


@pytest.mark.asyncio
async def test_export_contract_denies_employee(client, export_contract_data):
    employee = export_contract_data["users"]["employee"]
    token = _token_for(employee)

    response = await client.get(
        "/api/v1/transactions/export?format=csv",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "INSUFFICIENT_ROLE"


@pytest.mark.asyncio
async def test_export_contract_rejects_pdf_for_now(client, export_contract_data):
    admin = export_contract_data["users"]["admin"]
    token = _token_for(admin)

    response = await client.get(
        "/api/v1/transactions/export?format=pdf",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "EXPORT_FORMAT_NOT_SUPPORTED"


@pytest.mark.asyncio
async def test_export_contract_manager_branch_scope_overrides_filter(client, export_contract_data):
    manager = export_contract_data["users"]["manager"]
    branch_b = export_contract_data["branches"]["b"]
    token = _token_for(manager)

    response = await client.get(
        f"/api/v1/transactions/export?format=csv&branch_id={branch_b.id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    rows = _read_csv(response)
    assert len(rows) == 3
    assert {row["Sede"] for row in rows} == {"Sede A", "Sede B"}
    assert {row["Sede destino"] for row in rows} == {"-", "Sede A"}


@pytest.mark.asyncio
async def test_export_contract_contains_spanish_labels_and_formatted_values(client, export_contract_data):
    admin = export_contract_data["users"]["admin"]
    token = _token_for(admin)

    response = await client.get(
        "/api/v1/transactions/export?format=csv",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    rows = _read_csv(response)

    first_row = rows[0]
    assert set(first_row.keys()) == {
        "Id",
        "Tipo",
        "Sede",
        "Sede destino",
        "Fecha y hora",
        "Descripción",
        "Estado",
        "Creada por",
        "Artículo",
        "Cantidad",
        "Unidad",
    }

    all_types = {row["Tipo"] for row in rows}
    all_statuses = {row["Estado"] for row in rows}
    all_units = {row["Unidad"] for row in rows}
    all_creators = {row["Creada por"] for row in rows}
    all_quantities = {row["Cantidad"] for row in rows}
    all_ids = {row["Id"] for row in rows}

    assert all_types == {"Entrada", "Salida", "Traspaso"}
    assert all_statuses == {"Pendiente", "En tránsito"}
    assert all_units == {"ud", "kg"}
    assert all_creators == {"Admin Export", "Manager Export"}
    assert all("/" in row["Fecha y hora"] and ":" in row["Fecha y hora"] for row in rows)
    assert all_quantities == {"1", "2", "3", "5.5"}
    assert all(id_val.isdigit() for id_val in all_ids)


@pytest.mark.asyncio
async def test_export_contract_filters_by_search(client, export_contract_data):
    admin = export_contract_data["users"]["admin"]
    token = _token_for(admin)

    response = await client.get(
        "/api/v1/transactions/export?format=csv&search=Harina",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    rows = _read_csv(response)
    assert len(rows) == 2
    assert {row["Artículo"] for row in rows} == {"Articulo Export", "Harina Export"}


@pytest.mark.asyncio
async def test_export_contract_filters_by_date_range(client, export_contract_data):
    admin = export_contract_data["users"]["admin"]
    token = _token_for(admin)
    start_date, end_date = _dates_for_fixture()

    response = await client.get(
        f"/api/v1/transactions/export?format=csv&start_date={start_date}&end_date={end_date}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    rows = _read_csv(response)
    # Only transaction_branch_b (1 line) and transaction_to_branch_a (2 lines) fit this range.
    assert len(rows) == 3
    assert {row["Tipo"] for row in rows} == {"Salida", "Traspaso"}


@pytest.mark.asyncio
async def test_export_contract_orders_by_total_items_desc(client, export_contract_data):
    admin = export_contract_data["users"]["admin"]
    token = _token_for(admin)

    response = await client.get(
        "/api/v1/transactions/export?format=csv&order_by=total_items&order_desc=true",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    rows = _read_csv(response)
    # The first transaction in this ordering is TRANSFER with two lines.
    assert rows[0]["Tipo"] == "Traspaso"
    assert rows[1]["Tipo"] == "Traspaso"


@pytest.mark.asyncio
async def test_export_contract_rejects_export_exceeding_line_limit(client, db_session, export_contract_data):
    admin = export_contract_data["users"]["admin"]
    branch_a = export_contract_data["branches"]["a"]
    company = export_contract_data["branches"]["a"].company
    item = (
        db_session.query(Item)
        .filter(Item.company_id == company.id)
        .first()
    )
    token = _token_for(admin)

    # Generate a transaction with 50001 lines to exceed the limit
    big_transaction = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.PENDING,
        created_at=datetime.utcnow(),
        description="Bulk transaction",
        branch_id=branch_a.id,
    )
    db_session.add(big_transaction)
    db_session.flush()

    # Add 50001 lines to exceed EXPORT_MAX_LINES (50000)
    for i in range(50001):
        db_session.add(
            TransactionLine(
                quantity=Decimal("1.000"),
                item_id=item.id,
                transaction_id=big_transaction.id,
            )
        )
    db_session.add(
        TransactionEvent(
            action_type=ActionType.CREATED,
            timestamp=datetime.utcnow(),
            transaction_id=big_transaction.id,
            performed_by=admin.id,
        )
    )
    db_session.commit()

    response = await client.get(
        "/api/v1/transactions/export?format=csv",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 400
    assert "EXPORT_EXCEEDS_LIMIT_50000" in response.json()["detail"]
