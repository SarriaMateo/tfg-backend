import pytest
from datetime import datetime, timedelta
from app.core.security import hash_password, create_access_token
from app.db.models.user import User, Role
from app.db.models.company import Company
from app.db.models.branch import Branch
from app.db.models.item import Item, Unit
from app.db.models.transaction import Transaction, OperationType, TransactionStatus
from app.db.models.transaction_line import TransactionLine
from app.db.models.transaction_event import TransactionEvent, ActionType
from app.db.models.stock_movement import StockMovement, MovementType


@pytest.fixture
def company_with_transactions_data(db_session):
    """Setup company with branches, items, and users for transaction tests"""
    company = Company(
        name="Transaction Company",
        email="transactions@company.com",
        nif="87654321A"
    )
    db_session.add(company)
    db_session.flush()

    # Create branches
    branch_a = Branch(name="Warehouse A", address="Street A", company_id=company.id, is_active=True)
    branch_b = Branch(name="Warehouse B", address="Street B", company_id=company.id, is_active=True)
    db_session.add_all([branch_a, branch_b])
    db_session.flush()

    # Create items
    item_1 = Item(
        name="Product A",
        sku="PROD001",
        unit=Unit.UNIT,
        is_active=True,
        company_id=company.id
    )
    item_2 = Item(
        name="Product B",
        sku="PROD002",
        unit=Unit.KILOGRAM,
        is_active=True,
        company_id=company.id
    )
    item_3 = Item(
        name="Product C",
        sku="PROD003",
        unit=Unit.UNIT,
        is_active=False,  # Inactive item
        company_id=company.id
    )
    db_session.add_all([item_1, item_2, item_3])
    db_session.flush()

    # Create users
    admin_user = User(
        name="Admin User",
        username="admin_trans",
        hashed_password=hash_password("password123"),
        role=Role.ADMIN,
        is_active=True,
        company_id=company.id,
        branch_id=None
    )
    
    employee_branch_a = User(
        name="Employee A",
        username="employee_a",
        hashed_password=hash_password("password123"),
        role=Role.EMPLOYEE,
        is_active=True,
        company_id=company.id,
        branch_id=branch_a.id
    )
    
    employee_no_branch = User(
        name="Employee No Branch",
        username="employee_no_branch",
        hashed_password=hash_password("password123"),
        role=Role.EMPLOYEE,
        is_active=True,
        company_id=company.id,
        branch_id=None
    )
    
    db_session.add_all([admin_user, employee_branch_a, employee_no_branch])
    db_session.commit()

    return {
        "company": company,
        "branches": [branch_a, branch_b],
        "items": [item_1, item_2, item_3],
        "users": {
            "admin": admin_user,
            "employee_branch_a": employee_branch_a,
            "employee_no_branch": employee_no_branch
        }
    }


def build_token(user: User) -> str:
    return create_access_token({
        "sub": user.username,
        "user_id": user.id,
        "role": user.role.value,
        "company_id": user.company_id,
        "branch_id": user.branch_id,
    })


# =============================================================================
# CREATE TRANSACTION TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_create_transaction_in_success(client, company_with_transactions_data):
    """Test creating an IN transaction successfully"""
    data = company_with_transactions_data
    user = data["users"]["admin"]
    branch = data["branches"][0]
    item1 = data["items"][0]
    item2 = data["items"][1]
    
    token = build_token(user)
    
    transaction_data = {
        "operation_type": "IN",
        "description": "Initial stock entry",
        "branch_id": branch.id,
        "lines": [
            {"quantity": 10, "item_id": item1.id},
            {"quantity": 5.5, "item_id": item2.id}
        ]
    }
    
    response = await client.post(
        "/api/v1/transactions",
        json=transaction_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 201
    result = response.json()
    assert result["operation_type"] == "IN"
    assert result["status"] == "PENDING"
    assert result["branch_id"] == branch.id
    assert len(result["lines"]) == 2
    assert result["description"] == "Initial stock entry"
    assert "has_document" not in result


@pytest.mark.asyncio
async def test_create_transaction_out_success(client, company_with_transactions_data):
    """Test creating an OUT transaction successfully"""
    data = company_with_transactions_data
    user = data["users"]["admin"]
    branch = data["branches"][0]
    item = data["items"][0]
    
    token = build_token(user)
    
    transaction_data = {
        "operation_type": "OUT",
        "description": "Stock removal",
        "branch_id": branch.id,
        "lines": [
            {"quantity": 5, "item_id": item.id}
        ]
    }
    
    response = await client.post(
        "/api/v1/transactions",
        json=transaction_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 201
    result = response.json()
    assert result["operation_type"] == "OUT"
    assert result["status"] == "PENDING"


@pytest.mark.asyncio
async def test_create_transaction_inactive_item_fails(client, company_with_transactions_data):
    """Test that creating transaction with inactive item fails"""
    data = company_with_transactions_data
    user = data["users"]["admin"]
    branch = data["branches"][0]
    inactive_item = data["items"][2]  # item_3 is inactive
    
    token = build_token(user)
    
    transaction_data = {
        "operation_type": "IN",
        "branch_id": branch.id,
        "lines": [
            {"quantity": 10, "item_id": inactive_item.id}
        ]
    }
    
    response = await client.post(
        "/api/v1/transactions",
        json=transaction_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "ITEM_INACTIVE"


@pytest.mark.asyncio
async def test_create_transaction_inactive_branch_fails(client, company_with_transactions_data, db_session):
    """Test that creating transaction with inactive branch fails"""
    data = company_with_transactions_data
    user = data["users"]["admin"]
    branch = data["branches"][0]
    item = data["items"][0]

    branch.is_active = False
    db_session.commit()

    token = build_token(user)

    transaction_data = {
        "operation_type": "IN",
        "branch_id": branch.id,
        "lines": [
            {"quantity": 10, "item_id": item.id}
        ]
    }

    response = await client.post(
        "/api/v1/transactions",
        json=transaction_data,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "BRANCH_INACTIVE"


@pytest.mark.asyncio
async def test_create_transaction_user_with_branch_cannot_use_other_branch(
    client, company_with_transactions_data
):
    """Test that user with assigned branch cannot create transaction in another branch"""
    data = company_with_transactions_data
    user = data["users"]["employee_branch_a"]  # Assigned to branch_a
    branch_b = data["branches"][1]  # Try to use branch_b
    item = data["items"][0]
    
    token = build_token(user)
    
    transaction_data = {
        "operation_type": "IN",
        "branch_id": branch_b.id,
        "lines": [
            {"quantity": 10, "item_id": item.id}
        ]
    }
    
    response = await client.post(
        "/api/v1/transactions",
        json=transaction_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 403
    assert "BRANCH_ACCESS_DENIED" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_transaction_integer_quantity_validation(
    client, company_with_transactions_data
):
    """Test that UNIT items must have integer quantities"""
    data = company_with_transactions_data
    user = data["users"]["admin"]
    branch = data["branches"][0]
    unit_item = data["items"][0]  # Unit.UNIT
    
    token = build_token(user)
    
    transaction_data = {
        "operation_type": "IN",
        "branch_id": branch.id,
        "lines": [
            {"quantity": 10.5, "item_id": unit_item.id}  # Decimal for UNIT item
        ]
    }
    
    response = await client.post(
        "/api/v1/transactions",
        json=transaction_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert "QUANTITY_MUST_BE_INTEGER" in response.json()["detail"]


@pytest.mark.asyncio
async def test_create_transaction_transfer_not_supported(
    client, company_with_transactions_data
):
    """Test that TRANSFER operation is not yet supported"""
    data = company_with_transactions_data
    user = data["users"]["admin"]
    branch = data["branches"][0]
    item = data["items"][0]
    
    token = build_token(user)
    
    transaction_data = {
        "operation_type": "TRANSFER",
        "branch_id": branch.id,
        "destination_branch_id": data["branches"][1].id,
        "lines": [
            {"quantity": 10, "item_id": item.id}
        ]
    }
    
    response = await client.post(
        "/api/v1/transactions",
        json=transaction_data,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert "OPERATION_TYPE_NOT_SUPPORTED" in response.json()["detail"]


# =============================================================================
# COMPLETE TRANSACTION TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_complete_transaction_in_creates_stock_movements(
    client, db_session, company_with_transactions_data
):
    """Test that completing IN transaction creates positive stock movements"""
    data = company_with_transactions_data
    user = data["users"]["admin"]
    branch = data["branches"][0]
    item = data["items"][0]
    
    # Create a pending transaction
    transaction = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.PENDING,
        branch_id=branch.id
    )
    db_session.add(transaction)
    db_session.flush()
    
    line = TransactionLine(
        quantity=10,
        item_id=item.id,
        transaction_id=transaction.id
    )
    db_session.add(line)
    
    event = TransactionEvent(
        action_type=ActionType.CREATED,
        transaction_id=transaction.id,
        performed_by=user.id
    )
    db_session.add(event)
    db_session.commit()
    
    token = build_token(user)
    
    response = await client.post(
        f"/api/v1/transactions/{transaction.id}/complete",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "COMPLETED"
    
    # Verify stock movement was created
    stock_movements = db_session.query(StockMovement).filter(
        StockMovement.transaction_id == transaction.id
    ).all()
    
    assert len(stock_movements) == 1
    assert stock_movements[0].quantity == 10  # Positive for IN
    assert stock_movements[0].item_id == item.id
    assert stock_movements[0].branch_id == branch.id


@pytest.mark.asyncio
async def test_complete_transaction_out_creates_negative_stock_movements(
    client, db_session, company_with_transactions_data
):
    """Test that completing OUT transaction creates negative stock movements"""
    data = company_with_transactions_data
    user = data["users"]["admin"]
    branch = data["branches"][0]
    item = data["items"][0]
    
    # First, add stock
    # Create a dummy transaction for the stock movement
    dummy_transaction = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.COMPLETED,
        branch_id=branch.id
    )
    db_session.add(dummy_transaction)
    db_session.flush()
    
    stock_in = StockMovement(
        quantity=20,
        movement_type=MovementType.IN,
        item_id=item.id,
        branch_id=branch.id,
        transaction_id=dummy_transaction.id
    )
    db_session.add(stock_in)
    db_session.flush()
    
    # Create a pending OUT transaction
    transaction = Transaction(
        operation_type=OperationType.OUT,
        status=TransactionStatus.PENDING,
        branch_id=branch.id
    )
    db_session.add(transaction)
    db_session.flush()
    
    line = TransactionLine(
        quantity=5,
        item_id=item.id,
        transaction_id=transaction.id
    )
    db_session.add(line)
    
    event = TransactionEvent(
        action_type=ActionType.CREATED,
        transaction_id=transaction.id,
        performed_by=user.id
    )
    db_session.add(event)
    db_session.commit()
    
    token = build_token(user)
    
    response = await client.post(
        f"/api/v1/transactions/{transaction.id}/complete",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "COMPLETED"
    
    # Verify stock movement was created with negative quantity
    stock_movements = db_session.query(StockMovement).filter(
        StockMovement.transaction_id == transaction.id
    ).all()
    
    assert len(stock_movements) == 1
    assert stock_movements[0].quantity == -5  # Negative for OUT
    assert stock_movements[0].item_id == item.id


@pytest.mark.asyncio
async def test_complete_transaction_out_insufficient_stock_fails(
    client, db_session, company_with_transactions_data
):
    """Test that completing OUT transaction with insufficient stock fails"""
    data = company_with_transactions_data
    user = data["users"]["admin"]
    branch = data["branches"][0]
    item = data["items"][0]
    
    # Create OUT transaction without having stock
    transaction = Transaction(
        operation_type=OperationType.OUT,
        status=TransactionStatus.PENDING,
        branch_id=branch.id
    )
    db_session.add(transaction)
    db_session.flush()
    
    line = TransactionLine(
        quantity=10,
        item_id=item.id,
        transaction_id=transaction.id
    )
    db_session.add(line)
    
    event = TransactionEvent(
        action_type=ActionType.CREATED,
        transaction_id=transaction.id,
        performed_by=user.id
    )
    db_session.add(event)
    db_session.commit()
    
    token = build_token(user)
    
    response = await client.post(
        f"/api/v1/transactions/{transaction.id}/complete",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert "INSUFFICIENT_STOCK" in response.json()["detail"]


# =============================================================================
# CANCEL TRANSACTION TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_cancel_transaction_success(
    client, db_session, company_with_transactions_data
):
    """Test cancelling a pending transaction"""
    data = company_with_transactions_data
    user = data["users"]["admin"]
    branch = data["branches"][0]
    item = data["items"][0]
    
    # Create pending transaction
    transaction = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.PENDING,
        branch_id=branch.id
    )
    db_session.add(transaction)
    db_session.flush()
    
    line = TransactionLine(
        quantity=10,
        item_id=item.id,
        transaction_id=transaction.id
    )
    db_session.add(line)
    
    event = TransactionEvent(
        action_type=ActionType.CREATED,
        transaction_id=transaction.id,
        performed_by=user.id
    )
    db_session.add(event)
    db_session.commit()
    
    token = build_token(user)
    
    response = await client.post(
        f"/api/v1/transactions/{transaction.id}/cancel",
        data={"cancel_reason": "Test cancellation"},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["status"] == "CANCELLED"
    
    # Verify CANCELLED event was created
    cancel_events = db_session.query(TransactionEvent).filter(
        TransactionEvent.transaction_id == transaction.id,
        TransactionEvent.action_type == ActionType.CANCELLED
    ).all()
    
    assert len(cancel_events) == 1
    assert cancel_events[0].event_metadata["reason"] == "Test cancellation"


@pytest.mark.asyncio
async def test_cannot_edit_cancelled_transaction(
    client, db_session, company_with_transactions_data
):
    """Test that cancelled transaction cannot be edited"""
    data = company_with_transactions_data
    user = data["users"]["admin"]
    branch = data["branches"][0]
    item = data["items"][0]
    
    # Create cancelled transaction
    transaction = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.CANCELLED,
        branch_id=branch.id
    )
    db_session.add(transaction)
    db_session.flush()
    
    line = TransactionLine(
        quantity=10,
        item_id=item.id,
        transaction_id=transaction.id
    )
    db_session.add(line)
    db_session.commit()
    
    token = build_token(user)
    
    response = await client.put(
        f"/api/v1/transactions/{transaction.id}",
        data={"description": "Try to edit"},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert "TRANSACTION_NOT_EDITABLE" in response.json()["detail"]


@pytest.mark.asyncio
async def test_cannot_complete_cancelled_transaction(
    client, db_session, company_with_transactions_data
):
    """Test that cancelled transaction cannot be completed"""
    data = company_with_transactions_data
    user = data["users"]["admin"]
    branch = data["branches"][0]
    item = data["items"][0]
    
    # Create cancelled transaction
    transaction = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.CANCELLED,
        branch_id=branch.id
    )
    db_session.add(transaction)
    db_session.flush()
    
    line = TransactionLine(
        quantity=10,
        item_id=item.id,
        transaction_id=transaction.id
    )
    db_session.add(line)
    db_session.commit()
    
    token = build_token(user)
    
    response = await client.post(
        f"/api/v1/transactions/{transaction.id}/complete",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert "TRANSACTION_NOT_EDITABLE" in response.json()["detail"]


# =============================================================================
# UPDATE TRANSACTION TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_update_transaction_description(
    client, db_session, company_with_transactions_data
):
    """Test updating transaction description"""
    data = company_with_transactions_data
    user = data["users"]["admin"]
    branch = data["branches"][0]
    item = data["items"][0]
    
    # Create pending transaction
    transaction = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.PENDING,
        description="Original description",
        branch_id=branch.id
    )
    db_session.add(transaction)
    db_session.flush()
    
    line = TransactionLine(
        quantity=10,
        item_id=item.id,
        transaction_id=transaction.id
    )
    db_session.add(line)
    
    event = TransactionEvent(
        action_type=ActionType.CREATED,
        transaction_id=transaction.id,
        performed_by=user.id
    )
    db_session.add(event)
    db_session.commit()
    
    token = build_token(user)
    
    response = await client.put(
        f"/api/v1/transactions/{transaction.id}",
        data={"description": "Updated description"},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["description"] == "Updated description"
    
    # Verify EDITED event was created
    edit_events = db_session.query(TransactionEvent).filter(
        TransactionEvent.transaction_id == transaction.id,
        TransactionEvent.action_type == ActionType.EDITED
    ).all()
    
    assert len(edit_events) == 1


# =============================================================================
# LIST TRANSACTIONS TESTS
# =============================================================================

@pytest.mark.asyncio
async def test_list_transactions_pagination(
    client, db_session, company_with_transactions_data
):
    """Test listing transactions with pagination"""
    data = company_with_transactions_data
    user = data["users"]["admin"]
    branch = data["branches"][0]
    item = data["items"][0]
    
    # Create multiple transactions
    for i in range(5):
        transaction = Transaction(
            operation_type=OperationType.IN,
            status=TransactionStatus.PENDING,
            branch_id=branch.id
        )
        db_session.add(transaction)
        db_session.flush()
        
        line = TransactionLine(
            quantity=10,
            item_id=item.id,
            transaction_id=transaction.id
        )
        db_session.add(line)
    
    db_session.commit()
    
    token = build_token(user)
    
    response = await client.get(
        "/api/v1/transactions?page=1&page_size=3",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 5
    assert len(result["data"]) == 3
    assert result["page_size"] == 3
    assert result["total_pages"] == 2


@pytest.mark.asyncio
async def test_list_transactions_filter_by_status(
    client, db_session, company_with_transactions_data
):
    """Test filtering transactions by status"""
    data = company_with_transactions_data
    user = data["users"]["admin"]
    branch = data["branches"][0]
    item = data["items"][0]
    
    # Create transactions with different statuses
    pending_tx = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.PENDING,
        branch_id=branch.id
    )
    db_session.add(pending_tx)
    db_session.flush()
    
    completed_tx = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.COMPLETED,
        branch_id=branch.id
    )
    db_session.add(completed_tx)
    db_session.flush()
    
    for tx in [pending_tx, completed_tx]:
        line = TransactionLine(quantity=10, item_id=item.id, transaction_id=tx.id)
        db_session.add(line)
    
    db_session.commit()
    
    token = build_token(user)
    
    response = await client.get(
        "/api/v1/transactions?status=PENDING",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 1
    assert result["data"][0]["status"] == "PENDING"


@pytest.mark.asyncio
async def test_user_with_branch_only_sees_own_branch_transactions(
    client, db_session, company_with_transactions_data
):
    """Test that user with assigned branch only sees transactions from that branch"""
    data = company_with_transactions_data
    user = data["users"]["employee_branch_a"]  # Assigned to branch_a
    branch_a = data["branches"][0]
    branch_b = data["branches"][1]
    item = data["items"][0]
    
    # Create transaction in branch_a
    tx_a = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.PENDING,
        branch_id=branch_a.id
    )
    db_session.add(tx_a)
    db_session.flush()
    
    # Create transaction in branch_b
    tx_b = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.PENDING,
        branch_id=branch_b.id
    )
    db_session.add(tx_b)
    db_session.flush()
    
    for tx in [tx_a, tx_b]:
        line = TransactionLine(quantity=10, item_id=item.id, transaction_id=tx.id)
        db_session.add(line)
    
    db_session.commit()
    
    token = build_token(user)
    
    response = await client.get(
        "/api/v1/transactions",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 1  # Only sees branch_a transaction
    assert result["data"][0]["branch_id"] == branch_a.id


@pytest.mark.asyncio
async def test_list_transactions_user_branch_overrides_branch_filter_param(
    client, db_session, company_with_transactions_data
):
    """Test that branch filter param is ignored for users assigned to a specific branch"""
    data = company_with_transactions_data
    user = data["users"]["employee_branch_a"]
    branch_a = data["branches"][0]
    branch_b = data["branches"][1]
    item = data["items"][0]

    tx_a = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.PENDING,
        branch_id=branch_a.id
    )
    db_session.add(tx_a)
    db_session.flush()

    tx_b = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.PENDING,
        branch_id=branch_b.id
    )
    db_session.add(tx_b)
    db_session.flush()

    for tx in [tx_a, tx_b]:
        db_session.add(TransactionLine(quantity=10, item_id=item.id, transaction_id=tx.id))

    db_session.commit()

    token = build_token(user)

    response = await client.get(
        f"/api/v1/transactions?branch_id={branch_b.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 1
    assert result["data"][0]["branch_id"] == branch_a.id


@pytest.mark.asyncio
async def test_list_transactions_filter_by_date_range(
    client, db_session, company_with_transactions_data
):
    """Test filtering transactions by start_date and end_date"""
    data = company_with_transactions_data
    user = data["users"]["admin"]
    branch = data["branches"][0]
    item = data["items"][0]

    base_date = datetime.utcnow().replace(hour=12, minute=0, second=0, microsecond=0)

    tx_old = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.PENDING,
        branch_id=branch.id,
        created_at=base_date - timedelta(days=5)
    )
    tx_in_range = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.PENDING,
        branch_id=branch.id,
        created_at=base_date - timedelta(days=2)
    )
    tx_new = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.PENDING,
        branch_id=branch.id,
        created_at=base_date
    )

    db_session.add_all([tx_old, tx_in_range, tx_new])
    db_session.flush()

    for tx in [tx_old, tx_in_range, tx_new]:
        db_session.add(TransactionLine(quantity=10, item_id=item.id, transaction_id=tx.id))

    db_session.commit()

    token = build_token(user)
    start_date = (base_date - timedelta(days=3)).date().isoformat()
    end_date = (base_date - timedelta(days=1)).date().isoformat()

    response = await client.get(
        f"/api/v1/transactions?start_date={start_date}&end_date={end_date}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    result = response.json()
    assert result["total"] == 1
    assert result["data"][0]["id"] == tx_in_range.id
    assert "has_document" not in result["data"][0]
