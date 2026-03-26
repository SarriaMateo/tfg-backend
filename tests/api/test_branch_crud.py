import pytest
from app.core.security import hash_password, create_access_token
from app.db.models.user import Role, User
from app.db.models.company import Company
from app.db.models.branch import Branch
from app.db.models.transaction import Transaction, OperationType


@pytest.fixture
def admin_user(db_session):
    """Create an admin user for tests"""
    company = Company(
        name="Test Company",
        email="test@company.com",
        nif="12345678A"
    )
    db_session.add(company)
    db_session.flush()

    user = User(
        name="Admin User",
        username="admin_user",
        hashed_password=hash_password("admin123"),
        role=Role.ADMIN,
        company_id=company.id,
        branch_id=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def employee_no_branch(db_session, admin_user):
    """Create an employee without branch"""
    user = User(
        name="Employee No Branch",
        username="emp_no_branch",
        hashed_password=hash_password("emp123"),
        role=Role.EMPLOYEE,
        company_id=admin_user.company_id,
        branch_id=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def branch_with_employee(db_session, admin_user):
    """Create a branch and assign an employee to it"""
    branch = Branch(
        name="Branch With Employee",
        address="123 Employee St",
        company_id=admin_user.company_id
    )
    db_session.add(branch)
    db_session.flush()

    employee = User(
        name="Employee With Branch",
        username="emp_with_branch",
        hashed_password=hash_password("emp123"),
        role=Role.EMPLOYEE,
        company_id=admin_user.company_id,
        branch_id=branch.id,
    )
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(branch)
    return branch


@pytest.fixture
def branch_empty(db_session, admin_user):
    """Create an empty branch"""
    branch = Branch(
        name="Empty Branch",
        address="456 Empty Ave",
        company_id=admin_user.company_id
    )
    db_session.add(branch)
    db_session.commit()
    db_session.refresh(branch)
    return branch


@pytest.fixture
def inactive_branch(db_session, admin_user):
    """Create an inactive branch"""
    branch = Branch(
        name="Inactive Branch",
        address="789 Inactive St",
        company_id=admin_user.company_id,
        is_active=False
    )
    db_session.add(branch)
    db_session.commit()
    db_session.refresh(branch)
    return branch


@pytest.fixture
def other_company_admin(db_session):
    """Create an admin from another company"""
    company = Company(
        name="Other Company",
        email="other@company.com",
        nif="87654321B"
    )
    db_session.add(company)
    db_session.flush()

    user = User(
        name="Other Admin",
        username="other_admin",
        hashed_password=hash_password("other123"),
        role=Role.ADMIN,
        company_id=company.id,
        branch_id=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def get_admin_token(admin_user):
    """Helper to get admin token"""
    return create_access_token({
        "sub": admin_user.username,
        "user_id": admin_user.id,
        "role": admin_user.role.value,
        "company_id": admin_user.company_id,
        "branch_id": admin_user.branch_id,
    })


def get_token(user):
    """Helper to get user token"""
    return create_access_token({
        "sub": user.username,
        "user_id": user.id,
        "role": user.role.value,
        "company_id": user.company_id,
        "branch_id": user.branch_id,
    })


# ==================== CREATE TESTS ====================

@pytest.mark.asyncio
async def test_create_branch_success(client, admin_user):
    """An admin can create a branch in their company"""
    token = get_admin_token(admin_user)
    
    payload = {
        "name": "New Branch",
        "address": "789 New St"
    }
    
    response = await client.post(
        "/api/v1/branches",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New Branch"
    assert data["address"] == "789 New St"
    assert data["company_id"] == admin_user.company_id


@pytest.mark.asyncio
async def test_create_branch_non_admin(client, employee_no_branch):
    """An employee cannot create branches"""
    token = get_token(employee_no_branch)
    
    payload = {
        "name": "New Branch",
        "address": "789 New St"
    }
    
    response = await client.post(
        "/api/v1/branches",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 403
    assert response.json()["detail"] == "INSUFFICIENT_ROLE"


@pytest.mark.asyncio
async def test_create_branch_different_company(client, admin_user, other_company_admin):
    """An admin cannot create branches in another company via authenticated company"""
    # This test verifies that company isolation is enforced via authentication
    token = get_admin_token(other_company_admin)
    
    payload = {
        "name": "New Branch",
        "address": "789 New St"
    }
    
    response = await client.post(
        "/api/v1/branches",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Should succeed but be created in OTHER company's space
    assert response.status_code == 201
    data = response.json()
    assert data["company_id"] == other_company_admin.company_id  # Not admin_user's company


@pytest.mark.asyncio
async def test_create_branch_name_too_short(client, admin_user):
    """Branch name must be at least 3 characters"""
    token = get_admin_token(admin_user)
    
    payload = {
        "name": "AB",  # Too short
        "address": "789 New St"
    }
    
    response = await client.post(
        "/api/v1/branches",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_create_branch_address_too_short(client, admin_user):
    """Branch address must be at least 5 characters"""
    token = get_admin_token(admin_user)
    
    payload = {
        "name": "New Branch",
        "address": "123"  # Too short
    }
    
    response = await client.post(
        "/api/v1/branches",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_branch_duplicate_name(client, admin_user, branch_empty):
    """Cannot create two branches with the same name in the same company"""
    token = get_admin_token(admin_user)
    
    payload = {
        "name": "Empty Branch",  # Same name as branch_empty
        "address": "Different Address 999"
    }
    
    response = await client.post(
        "/api/v1/branches",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 409
    assert response.json()["detail"] == "BRANCH_NAME_ALREADY_EXISTS"


# ==================== READ TESTS ====================

@pytest.mark.asyncio
async def test_get_branch_admin(client, admin_user, branch_empty):
    """An admin can view branches from their company"""
    token = get_admin_token(admin_user)
    
    response = await client.get(
        f"/api/v1/branches/{branch_empty.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == branch_empty.id
    assert data["name"] == "Empty Branch"


@pytest.mark.asyncio
async def test_get_branch_employee_no_branch(client, employee_no_branch, branch_empty):
    """An employee without branch can view any branch from their company"""
    token = get_token(employee_no_branch)
    
    response = await client.get(
        f"/api/v1/branches/{branch_empty.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == branch_empty.id


@pytest.mark.asyncio
async def test_get_branch_employee_own_branch(client, branch_with_employee):
    """An employee can view their own assigned branch"""
    employee = branch_with_employee.users[0]
    token = get_token(employee)
    
    response = await client.get(
        f"/api/v1/branches/{branch_with_employee.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == branch_with_employee.id


@pytest.mark.asyncio
async def test_get_branch_employee_different_branch(client, employee_no_branch, branch_with_employee, db_session):
    """An employee assigned to a branch cannot view other branches"""
    # Assign employee to a different branch
    new_branch = Branch(
        name="Employee Branch",
        address="999 Employee Way",
        company_id=employee_no_branch.company_id
    )
    db_session.add(new_branch)
    db_session.flush()
    
    employee_no_branch.branch_id = new_branch.id
    db_session.commit()
    
    token = get_token(employee_no_branch)
    
    response = await client.get(
        f"/api/v1/branches/{branch_with_employee.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 403
    assert response.json()["detail"] == "BRANCH_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_get_branch_not_found(client, admin_user):
    """Get non-existent branch"""
    token = get_admin_token(admin_user)
    
    response = await client.get(
        "/api/v1/branches/99999",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404
    assert response.json()["detail"] == "BRANCH_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_branches_by_company_admin(client, admin_user, branch_empty, branch_with_employee):
    """An admin can view all branches from their company"""
    token = get_admin_token(admin_user)
    
    response = await client.get(
        "/api/v1/branches",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    branch_names = [b["name"] for b in data]
    assert "Empty Branch" in branch_names
    assert "Branch With Employee" in branch_names


@pytest.mark.asyncio
async def test_get_branches_by_company_employee_no_branch(client, employee_no_branch, branch_empty, branch_with_employee):
    """An employee without branch can view all branches from their company"""
    token = get_token(employee_no_branch)
    
    response = await client.get(
        "/api/v1/branches",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2


@pytest.mark.asyncio
async def test_get_branches_by_company_employee_with_branch(client, branch_with_employee, branch_empty):
    """An employee assigned to a branch can view all company branches"""
    employee = branch_with_employee.users[0]
    token = get_token(employee)
    
    response = await client.get(
        "/api/v1/branches",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    branch_ids = [b["id"] for b in data]
    assert branch_with_employee.id in branch_ids
    assert branch_empty.id in branch_ids


@pytest.mark.asyncio
async def test_get_branches_employee_only_sees_active_branches(client, employee_no_branch, branch_with_employee, inactive_branch):
    """An employee always sees only active branches"""
    token = get_token(employee_no_branch)
    
    response = await client.get(
        "/api/v1/branches",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    # Should have branch_with_employee (active), but NOT inactive_branch
    assert len(data) == 1
    assert data[0]["name"] == "Branch With Employee"
    assert inactive_branch.id not in [b["id"] for b in data]


@pytest.mark.asyncio
async def test_get_branches_admin_sees_all_by_default(client, admin_user, branch_with_employee, inactive_branch):
    """An admin sees all branches by default (active and inactive)"""
    token = get_admin_token(admin_user)
    
    response = await client.get(
        "/api/v1/branches",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    # Should have branch_with_employee (active) + inactive_branch
    assert len(data) == 2
    branch_ids = [b["id"] for b in data]
    assert branch_with_employee.id in branch_ids
    assert inactive_branch.id in branch_ids


@pytest.mark.asyncio
async def test_get_branches_admin_filters_by_is_active_true(client, admin_user, branch_with_employee, inactive_branch):
    """An admin can filter to see only active branches"""
    token = get_admin_token(admin_user)
    
    response = await client.get(
        "/api/v1/branches?is_active=true",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    # Should only have active branches
    assert len(data) == 1
    assert data[0]["id"] == branch_with_employee.id
    assert inactive_branch.id not in [b["id"] for b in data]


@pytest.mark.asyncio
async def test_get_branches_admin_filters_by_is_active_false(client, admin_user, inactive_branch):
    """An admin can filter to see only inactive branches"""
    token = get_admin_token(admin_user)
    
    response = await client.get(
        "/api/v1/branches?is_active=false",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    # Should only have inactive branches
    assert len(data) == 1
    assert data[0]["id"] == inactive_branch.id


# ==================== UPDATE TESTS ====================

@pytest.mark.asyncio
async def test_update_branch_success(client, admin_user, branch_empty):
    """An admin can update a branch"""
    token = get_admin_token(admin_user)
    
    payload = {
        "name": "Updated Branch",
        "address": "Updated Address 789"
    }
    
    response = await client.put(
        f"/api/v1/branches/{branch_empty.id}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Branch"
    assert data["address"] == "Updated Address 789"


@pytest.mark.asyncio
async def test_update_branch_partial(client, admin_user, branch_empty):
    """An admin can partially update a branch"""
    token = get_admin_token(admin_user)
    
    payload = {
        "name": "Only Name Changed"
    }
    
    response = await client.put(
        f"/api/v1/branches/{branch_empty.id}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Only Name Changed"
    assert data["address"] == "456 Empty Ave"  # Unchanged


@pytest.mark.asyncio
async def test_update_branch_non_admin(client, employee_no_branch, branch_empty):
    """An employee cannot update branches"""
    token = get_token(employee_no_branch)
    
    payload = {
        "name": "Hacked Branch"
    }
    
    response = await client.put(
        f"/api/v1/branches/{branch_empty.id}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 403
    assert response.json()["detail"] == "INSUFFICIENT_ROLE"


@pytest.mark.asyncio
async def test_update_branch_duplicate_name(client, admin_user, branch_empty, branch_with_employee):
    """Cannot update branch to have the same name as another branch in the same company"""
    token = get_admin_token(admin_user)
    
    payload = {
        "name": "Branch With Employee"  # Same name as branch_with_employee
    }
    
    response = await client.put(
        f"/api/v1/branches/{branch_empty.id}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 409
    assert response.json()["detail"] == "BRANCH_NAME_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_update_branch_different_company(client, admin_user, branch_empty, other_company_admin):
    """An admin cannot update branches from another company via authenticated company"""
    # This test verifies that company isolation is enforced via authentication
    token = get_admin_token(other_company_admin)
    
    payload = {
        "name": "Hacked Branch"
    }
    
    response = await client.put(
        f"/api/v1/branches/{branch_empty.id}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Should fail because branch belongs to admin_user's company, not other_company_admin's
    assert response.status_code == 403
    assert response.json()["detail"] == "COMPANY_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_update_branch_not_found(client, admin_user):
    """Update non-existent branch"""
    token = get_admin_token(admin_user)
    
    payload = {
        "name": "Updated Branch"
    }
    
    response = await client.put(
        "/api/v1/branches/99999",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404
    assert response.json()["detail"] == "BRANCH_NOT_FOUND"


# ==================== DELETE TESTS ====================

@pytest.mark.asyncio
async def test_delete_branch_success(client, admin_user, branch_empty):
    """An admin can delete an empty branch"""
    token = get_admin_token(admin_user)
    
    response = await client.delete(
        f"/api/v1/branches/{branch_empty.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_branch_with_users(client, admin_user, branch_with_employee):
    """Cannot delete a branch that has users"""
    token = get_admin_token(admin_user)
    
    response = await client.delete(
        f"/api/v1/branches/{branch_with_employee.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "BRANCH_HAS_USERS"


@pytest.mark.asyncio
async def test_delete_branch_with_transactions(client, admin_user, branch_empty, db_session):
    """Cannot delete a branch that has transactions"""
    transaction = Transaction(
        operation_type=OperationType.IN,
        branch_id=branch_empty.id,
    )
    db_session.add(transaction)
    db_session.commit()

    token = get_admin_token(admin_user)

    response = await client.delete(
        f"/api/v1/branches/{branch_empty.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "BRANCH_HAS_TRANSACTIONS"


@pytest.mark.asyncio
async def test_delete_branch_with_transactions_as_destination(client, admin_user, branch_empty, db_session):
    """Cannot delete a branch referenced as destination branch in transfers"""
    origin_branch = Branch(
        name="Origin Branch",
        address="Origin Street",
        company_id=admin_user.company_id,
    )
    db_session.add(origin_branch)
    db_session.flush()

    transfer = Transaction(
        operation_type=OperationType.TRANSFER,
        branch_id=origin_branch.id,
        destination_branch_id=branch_empty.id,
    )
    db_session.add(transfer)
    db_session.commit()

    token = get_admin_token(admin_user)

    response = await client.delete(
        f"/api/v1/branches/{branch_empty.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "BRANCH_HAS_TRANSACTIONS"


@pytest.mark.asyncio
async def test_delete_branch_non_admin(client, employee_no_branch, branch_empty):
    """An employee cannot delete branches"""
    token = get_token(employee_no_branch)
    
    response = await client.delete(
        f"/api/v1/branches/{branch_empty.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 403
    assert response.json()["detail"] == "INSUFFICIENT_ROLE"


@pytest.mark.asyncio
async def test_delete_branch_different_company(client, admin_user, branch_empty, other_company_admin):
    """An admin cannot delete branches from another company via authenticated company"""
    # This test verifies that company isolation is enforced via authentication
    token = get_admin_token(other_company_admin)
    
    response = await client.delete(
        f"/api/v1/branches/{branch_empty.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Should fail because branch belongs to admin_user's company, not other_company_admin's
    assert response.status_code == 403
    assert response.json()["detail"] == "COMPANY_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_delete_branch_not_found(client, admin_user):
    """Delete non-existent branch"""
    token = get_admin_token(admin_user)
    
    response = await client.delete(
        "/api/v1/branches/99999",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404
    assert response.json()["detail"] == "BRANCH_NOT_FOUND"
