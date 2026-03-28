import pytest
from datetime import datetime
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
    db_session.add(item)
    db_session.flush()

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
        created_at=datetime.utcnow(),
        description="Entrada sede A",
        branch_id=branch_a.id,
    )
    transaction_branch_b = Transaction(
        operation_type=OperationType.OUT,
        status=TransactionStatus.PENDING,
        created_at=datetime.utcnow(),
        description="Salida sede B",
        branch_id=branch_b.id,
    )
    transaction_to_branch_a = Transaction(
        operation_type=OperationType.TRANSFER,
        status=TransactionStatus.TRANSIT,
        created_at=datetime.utcnow(),
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
                timestamp=datetime.utcnow(),
                transaction_id=transaction_branch_a.id,
                performed_by=admin.id,
            ),
            TransactionEvent(
                action_type=ActionType.CREATED,
                timestamp=datetime.utcnow(),
                transaction_id=transaction_branch_b.id,
                performed_by=admin.id,
            ),
            TransactionEvent(
                action_type=ActionType.CREATED,
                timestamp=datetime.utcnow(),
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
    # Three transactions with one line each -> three CSV rows.
    assert len(rows) == 3


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
    assert len(rows) == 2
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

    assert all_types == {"Entrada", "Salida", "Traspaso"}
    assert all_statuses == {"Pendiente", "En tránsito"}
    assert all_units == {"ud"}
    assert all_creators == {"admin_export", "manager_export"}
    assert all("/" in row["Fecha y hora"] and ":" in row["Fecha y hora"] for row in rows)
    assert all(row["Cantidad"] in {"1", "2", "3"} for row in rows)
