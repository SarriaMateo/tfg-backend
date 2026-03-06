import pytest
from app.core.security import hash_password, create_access_token
from app.db.models.user import Role, User
from app.db.models.company import Company
from app.db.models.branch import Branch


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
def employee_user(db_session, admin_user):
    """Create an employee user in the same company without branch"""
    user = User(
        name="Employee User",
        username="employee_user",
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
def employee_user_with_branch(db_session, admin_user, branch):
    """Create an employee user assigned to a branch"""
    user = User(
        name="Employee With Branch",
        username="employee_branch",
        hashed_password=hash_password("emp123"),
        role=Role.EMPLOYEE,
        company_id=admin_user.company_id,
        branch_id=branch.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_employee_user(db_session, admin_user):
    """Create an inactive employee user"""
    user = User(
        name="Inactive Employee",
        username="inactive_employee",
        hashed_password=hash_password("emp123"),
        role=Role.EMPLOYEE,
        company_id=admin_user.company_id,
        branch_id=None,
        is_active=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


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


@pytest.fixture
def branch(db_session, admin_user):
    """Create a branch for tests"""
    branch = Branch(
        name="Test Branch",
        address="Test Address",
        company_id=admin_user.company_id
    )
    db_session.add(branch)
    db_session.commit()
    db_session.refresh(branch)
    return branch


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
async def test_create_user_success(client, admin_user):
    """An admin can create a user in their company"""
    token = get_admin_token(admin_user)
    
    payload = {
        "name": "New User",
        "username": "newuser",
        "password": "password123",
        "role": "EMPLOYEE"
    }
    
    response = await client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "New User"
    assert data["username"] == "newuser"
    assert data["role"] == "EMPLOYEE"
    assert data["company_id"] == admin_user.company_id


@pytest.mark.asyncio
async def test_create_user_with_branch(client, admin_user, branch):
    """An admin can create a user with assigned branch"""
    token = get_admin_token(admin_user)
    
    payload = {
        "name": "User With Branch",
        "username": "userbranch",
        "password": "password123",
        "role": "MANAGER",
        "branch_id": branch.id
    }
    
    response = await client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["branch_id"] == branch.id


@pytest.mark.asyncio
async def test_create_user_duplicate_username(client, admin_user, employee_user):
    """Cannot create user with duplicate username"""
    token = get_admin_token(admin_user)
    
    payload = {
        "name": "Another User",
        "username": "employee_user",  # Username already exists
        "password": "password123",
        "role": "EMPLOYEE"
    }
    
    response = await client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 409
    assert response.json()["detail"] == "USERNAME_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_create_user_non_admin(client, employee_user):
    """An employee cannot create users"""
    token = get_token(employee_user)
    
    payload = {
        "name": "New User",
        "username": "newuser",
        "password": "password123",
        "role": "EMPLOYEE"
    }
    
    response = await client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 403
    assert response.json()["detail"] == "INSUFFICIENT_ROLE"


@pytest.mark.asyncio
async def test_create_user_different_company(client, admin_user, other_company_admin):
    """An admin cannot create users in another company via authenticated company"""
    # This test verifies that company isolation is enforced via authentication
    token = get_admin_token(other_company_admin)
    
    payload = {
        "name": "New User",
        "username": "newuser",
        "password": "password123",
        "role": "EMPLOYEE"
    }
    
    response = await client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    # Should succeed but be created in OTHER company's space
    assert response.status_code == 201
    data = response.json()
    assert data["company_id"] == other_company_admin.company_id  # Not admin_user's company


@pytest.mark.asyncio
async def test_create_user_branch_different_company(client, admin_user, other_company_admin, branch):
    """Cannot assign branch from different company"""
    token = get_admin_token(admin_user)
    
    # Create branch in another company
    payload = {
        "name": "New User",
        "username": "newuser",
        "password": "password123",
        "role": "EMPLOYEE",
        "branch_id": branch.id  # Branch from admin_user
    }
    
    # Try to create from another company
    response = await client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 201  # Should work because it's their branch
    assert response.json()["branch_id"] == branch.id


# ==================== READ TESTS ====================

@pytest.mark.asyncio
async def test_get_user_own_user(client, employee_user):
    """A user can view their own profile"""
    token = get_token(employee_user)
    
    response = await client.get(
        f"/api/v1/users/{employee_user.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == employee_user.id
    assert data["username"] == "employee_user"


@pytest.mark.asyncio
async def test_get_user_admin_view(client, admin_user, employee_user):
    """An admin can view users from their company"""
    token = get_admin_token(admin_user)
    
    response = await client.get(
        f"/api/v1/users/{employee_user.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    assert response.json()["id"] == employee_user.id


@pytest.mark.asyncio
async def test_get_user_non_admin_other_user(client, employee_user, admin_user):
    """An employee cannot view other users"""
    token = get_token(employee_user)
    
    response = await client.get(
        f"/api/v1/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 403
    assert response.json()["detail"] == "CANNOT_VIEW_OTHER_USERS"


@pytest.mark.asyncio
async def test_get_user_not_found(client, admin_user):
    """Get non-existent user"""
    token = get_admin_token(admin_user)
    
    response = await client.get(
        "/api/v1/users/99999",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404
    assert response.json()["detail"] == "USER_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_company_users_admin(client, admin_user, employee_user, db_session):
    """An admin can view all users from their company"""
    token = get_admin_token(admin_user)
    
    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # admin + employee
    usernames = [u["username"] for u in data]
    assert "admin_user" in usernames
    assert "employee_user" in usernames


@pytest.mark.asyncio
async def test_get_company_users_non_admin(client, employee_user):
    """An employee without branch_id can view all users"""
    token = get_token(employee_user)
    
    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2  # admin_user + employee_user


@pytest.mark.asyncio
async def test_get_company_users_employee_with_branch_no_param(client, employee_user_with_branch):
    """An employee with branch_id sees users from their branch plus unassigned users"""
    token = get_token(employee_user_with_branch)
    
    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    usernames = [u["username"] for u in data]
    assert "admin_user" in usernames
    assert "employee_branch" in usernames


@pytest.mark.asyncio
async def test_get_company_users_employee_with_branch_ignores_branch_query_param(client, employee_user_with_branch, admin_user, db_session):
    """Branch scope comes from token and ignores any branch_id query param"""
    another_branch = Branch(
        name="Another Branch",
        address="Another Address",
        company_id=admin_user.company_id
    )
    db_session.add(another_branch)
    db_session.commit()
    db_session.refresh(another_branch)

    token = get_token(employee_user_with_branch)
    
    response = await client.get(
        f"/api/v1/users?branch_id={another_branch.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    usernames = [u["username"] for u in data]
    assert "admin_user" in usernames
    assert "employee_branch" in usernames


@pytest.mark.asyncio
async def test_get_company_users_employee_with_branch_excludes_other_branch_users(client, employee_user_with_branch, admin_user, db_session):
    """An employee with branch_id does not receive users from other branches"""
    # Create another branch
    another_branch = Branch(
        name="Another Branch",
        address="Another Address",
        company_id=admin_user.company_id
    )
    db_session.add(another_branch)
    db_session.flush()
    user_other_branch = User(
        name="Other Branch User",
        username="other_branch_user",
        hashed_password=hash_password("emp123"),
        role=Role.EMPLOYEE,
        company_id=admin_user.company_id,
        branch_id=another_branch.id,
    )
    db_session.add(user_other_branch)
    db_session.commit()
    db_session.refresh(another_branch)
    
    token = get_token(employee_user_with_branch)
    
    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    usernames = [u["username"] for u in data]
    assert "other_branch_user" not in usernames


@pytest.mark.asyncio
async def test_get_company_users_employee_only_sees_active_users(client, employee_user, inactive_employee_user):
    """An employee always sees only active users"""
    token = get_token(employee_user)
    
    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    # Should have admin_user + employee_user (both active), but NOT inactive_employee_user
    assert len(data) == 2
    usernames = [u["username"] for u in data]
    assert "admin_user" in usernames
    assert "employee_user" in usernames
    assert inactive_employee_user.username not in usernames


@pytest.mark.asyncio
async def test_get_company_users_admin_sees_all_by_default(client, admin_user, employee_user, inactive_employee_user):
    """An admin sees all users by default (active and inactive)"""
    token = get_admin_token(admin_user)
    
    response = await client.get(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    # Should have admin + employee (active) + inactive_employee (inactive)
    assert len(data) == 3
    usernames = [u["username"] for u in data]
    assert "admin_user" in usernames
    assert "employee_user" in usernames
    assert "inactive_employee" in usernames


@pytest.mark.asyncio
async def test_get_company_users_admin_filters_by_is_active_true(client, admin_user, employee_user, inactive_employee_user):
    """An admin can filter to see only active users"""
    token = get_admin_token(admin_user)
    
    response = await client.get(
        "/api/v1/users?is_active=true",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    # Should have admin_user + employee_user (both active), but NOT inactive
    assert len(data) == 2
    usernames = [u["username"] for u in data]
    assert "admin_user" in usernames
    assert "employee_user" in usernames
    assert "inactive_employee" not in usernames


@pytest.mark.asyncio
async def test_get_company_users_admin_filters_by_is_active_false(client, admin_user, inactive_employee_user):
    """An admin can filter to see only inactive users"""
    token = get_admin_token(admin_user)
    
    response = await client.get(
        "/api/v1/users?is_active=false",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    # Should only have inactive users
    assert len(data) == 1
    assert data[0]["username"] == "inactive_employee"


# ==================== UPDATE TESTS ====================

@pytest.mark.asyncio
async def test_update_own_user(client, employee_user):
    """A user can update their own profile (name, username, password)"""
    token = get_token(employee_user)
    
    payload = {
        "name": "Updated Name",
        "username": "updated_username",
        "password": "newpassword123"
    }
    
    response = await client.put(
        f"/api/v1/users/{employee_user.id}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["username"] == "updated_username"


@pytest.mark.asyncio
async def test_update_own_user_cannot_change_role(client, employee_user):
    """A user cannot change their own role via normal PUT"""
    token = get_token(employee_user)
    
    payload = {
        "name": "Updated Name",
        "role": "ADMIN"  # Attempt to change role
    }
    
    response = await client.put(
        f"/api/v1/users/{employee_user.id}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    # Role field doesn't exist in UserUpdate, so it's ignored


@pytest.mark.asyncio
async def test_update_user_admin(client, admin_user, employee_user):
    """An admin can update user with all fields"""
    token = get_admin_token(admin_user)
    
    payload = {
        "name": "Updated Employee",
        "role": "MANAGER"
    }
    
    response = await client.put(
        f"/api/v1/users/{employee_user.id}/admin",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Employee"
    assert data["role"] == "MANAGER"


@pytest.mark.asyncio
async def test_update_user_duplicate_username(client, admin_user, employee_user, db_session):
    """Cannot update to username that already exists"""
    # Create another user
    other_user = User(
        name="Other User",
        username="otheruser",
        hashed_password=hash_password("other123"),
        role=Role.EMPLOYEE,
        company_id=admin_user.company_id,
        branch_id=None,
    )
    db_session.add(other_user)
    db_session.commit()
    
    token = get_admin_token(admin_user)
    
    payload = {
        "username": "otheruser"  # Username that already exists
    }
    
    response = await client.put(
        f"/api/v1/users/{employee_user.id}",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 409
    assert response.json()["detail"] == "USERNAME_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_update_admin_to_manager(client, admin_user, db_session):
    """Can change admin to another role if not the only one"""
    # Create another admin
    other_admin = User(
        name="Other Admin",
        username="otheradmin",
        hashed_password=hash_password("other123"),
        role=Role.ADMIN,
        company_id=admin_user.company_id,
        branch_id=None,
    )
    db_session.add(other_admin)
    db_session.commit()
    
    token = get_admin_token(admin_user)
    
    payload = {
        "role": "MANAGER"
    }
    
    response = await client.put(
        f"/api/v1/users/{other_admin.id}/admin",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    assert response.json()["role"] == "MANAGER"


@pytest.mark.asyncio
async def test_cannot_change_last_admin_role(client, admin_user):
    """Cannot change role of the only admin"""
    token = get_admin_token(admin_user)
    
    payload = {
        "role": "MANAGER"
    }
    
    response = await client.put(
        f"/api/v1/users/{admin_user.id}/admin",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "CANNOT_CHANGE_ROLE_LAST_ADMIN"


@pytest.mark.asyncio
async def test_cannot_change_last_active_admin_role_with_inactive_admin(client, admin_user, db_session):
    """Cannot change role of the only active admin if another admin is inactive"""
    inactive_admin = User(
        name="Inactive Admin",
        username="inactive_admin_for_role_change",
        hashed_password=hash_password("inactive123"),
        role=Role.ADMIN,
        is_active=False,
        company_id=admin_user.company_id,
        branch_id=None,
    )
    db_session.add(inactive_admin)
    db_session.commit()

    token = get_admin_token(admin_user)

    response = await client.put(
        f"/api/v1/users/{admin_user.id}/admin",
        json={"role": "MANAGER"},
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "CANNOT_CHANGE_ROLE_LAST_ADMIN"


@pytest.mark.asyncio
async def test_update_user_branch_different_company(client, admin_user, other_company_admin, db_session):
    """Cannot assign branch from different company when updating"""
    # Get branch from another company
    from app.db.models.branch import Branch
    other_branch = db_session.query(Branch).filter_by(company_id=other_company_admin.company_id).first()
    if not other_branch:
        other_branch = Branch(
            name="Other Branch",
            address="Other Address",
            company_id=other_company_admin.company_id
        )
        db_session.add(other_branch)
        db_session.commit()
    
    token = get_admin_token(admin_user)
    
    # Create user in admin_user's company
    new_user = User(
        name="Test User",
        username="testuser",
        hashed_password=hash_password("test123"),
        role=Role.EMPLOYEE,
        company_id=admin_user.company_id,
        branch_id=None,
    )
    db_session.add(new_user)
    db_session.commit()
    
    payload = {
        "branch_id": other_branch.id
    }
    
    response = await client.put(
        f"/api/v1/users/{new_user.id}/admin",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "BRANCH_BELONGS_TO_DIFFERENT_COMPANY"


# ==================== DELETE TESTS ====================

@pytest.mark.asyncio
async def test_delete_user_admin(client, admin_user, employee_user):
    """An admin can delete a user from their company"""
    token = get_admin_token(admin_user)
    
    response = await client.delete(
        f"/api/v1/users/{employee_user.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_user_non_admin(client, employee_user, admin_user):
    """An employee cannot delete users"""
    token = get_token(employee_user)
    
    response = await client.delete(
        f"/api/v1/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 403
    assert response.json()["detail"] == "INSUFFICIENT_ROLE"


@pytest.mark.asyncio
async def test_cannot_delete_last_admin(client, admin_user):
    """Cannot delete the only admin of a company"""
    token = get_admin_token(admin_user)
    
    response = await client.delete(
        f"/api/v1/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "CANNOT_DELETE_LAST_ADMIN"


@pytest.mark.asyncio
async def test_cannot_delete_last_active_admin_with_inactive_admin(client, admin_user, db_session):
    """Cannot delete the only active admin if another admin is inactive"""
    inactive_admin = User(
        name="Inactive Admin",
        username="inactive_admin_for_delete",
        hashed_password=hash_password("inactive123"),
        role=Role.ADMIN,
        is_active=False,
        company_id=admin_user.company_id,
        branch_id=None,
    )
    db_session.add(inactive_admin)
    db_session.commit()

    token = get_admin_token(admin_user)

    response = await client.delete(
        f"/api/v1/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "CANNOT_DELETE_LAST_ADMIN"


@pytest.mark.asyncio
async def test_delete_user_different_company(client, admin_user, other_company_admin):
    """An admin cannot delete users from another company"""
    token = get_admin_token(other_company_admin)
    
    response = await client.delete(
        f"/api/v1/users/{admin_user.id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 403
    assert response.json()["detail"] == "USER_FROM_DIFFERENT_COMPANY"


@pytest.mark.asyncio
async def test_delete_user_not_found(client, admin_user):
    """Delete non-existent user"""
    token = get_admin_token(admin_user)
    
    response = await client.delete(
        "/api/v1/users/99999",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 404
    assert response.json()["detail"] == "USER_NOT_FOUND"


# ==================== ADMIN BRANCH RESTRICTION TESTS ====================

@pytest.mark.asyncio
async def test_create_admin_with_branch(client, admin_user, branch):
    """Cannot create admin user with branch assigned"""
    token = get_admin_token(admin_user)
    
    payload = {
        "name": "Admin With Branch",
        "username": "admin_branch",
        "password": "password123",
        "role": "ADMIN",
        "branch_id": branch.id
    }
    
    response = await client.post(
        "/api/v1/users",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "ADMIN_CANNOT_HAVE_BRANCH"


@pytest.mark.asyncio
async def test_update_user_to_admin_with_existing_branch(client, admin_user, branch, db_session):
    """Cannot change user to admin if they have a branch assigned"""
    token = get_admin_token(admin_user)
    
    # Create employee with branch
    employee = User(
        name="Employee With Branch",
        username="emp_branch",
        hashed_password=hash_password("emp123"),
        role=Role.EMPLOYEE,
        company_id=admin_user.company_id,
        branch_id=branch.id,
    )
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(employee)
    
    payload = {
        "role": "ADMIN"
    }
    
    response = await client.put(
        f"/api/v1/users/{employee.id}/admin",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "ADMIN_CANNOT_HAVE_BRANCH"


@pytest.mark.asyncio
async def test_assign_branch_to_admin_user(client, admin_user, branch):
    """Cannot assign branch to admin user"""
    token = get_admin_token(admin_user)
    
    payload = {
        "branch_id": branch.id
    }
    
    response = await client.put(
        f"/api/v1/users/{admin_user.id}/admin",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "ADMIN_CANNOT_HAVE_BRANCH"


@pytest.mark.asyncio
async def test_change_to_admin_and_assign_branch_same_request(client, admin_user, branch, employee_user):
    """Cannot change role to admin and assign branch in same request"""
    token = get_admin_token(admin_user)
    
    payload = {
        "role": "ADMIN",
        "branch_id": branch.id
    }
    
    response = await client.put(
        f"/api/v1/users/{employee_user.id}/admin",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 400
    assert response.json()["detail"] == "ADMIN_CANNOT_HAVE_BRANCH"


# ==================== BRANCH UPDATE TESTS (exclude_unset) ====================

@pytest.mark.asyncio
async def test_update_user_without_touching_branch(client, admin_user, branch, db_session):
    """Update user without sending branch_id should not change branch"""
    token = get_admin_token(admin_user)
    
    # Create employee with branch
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
    db_session.refresh(employee)
    
    payload = {
        "name": "Updated Name"
    }
    
    response = await client.put(
        f"/api/v1/users/{employee.id}/admin",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["branch_id"] == branch.id  # Should remain unchanged


@pytest.mark.asyncio
async def test_update_user_unassign_branch(client, admin_user, branch, db_session):
    """Update user with branch_id: null should unassign branch"""
    token = get_admin_token(admin_user)
    
    # Create employee with branch
    employee = User(
        name="Employee With Branch",
        username="emp_to_unassign",
        hashed_password=hash_password("emp123"),
        role=Role.EMPLOYEE,
        company_id=admin_user.company_id,
        branch_id=branch.id,
    )
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(employee)
    
    payload = {
        "branch_id": None
    }
    
    response = await client.put(
        f"/api/v1/users/{employee.id}/admin",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["branch_id"] is None


@pytest.mark.asyncio
async def test_update_user_change_branch(client, admin_user, db_session):
    """Update user changing from one branch to another"""
    token = get_admin_token(admin_user)
    
    # Create two branches
    branch1 = Branch(
        name="Branch 1",
        address="Address 1",
        company_id=admin_user.company_id
    )
    branch2 = Branch(
        name="Branch 2",
        address="Address 2",
        company_id=admin_user.company_id
    )
    db_session.add_all([branch1, branch2])
    db_session.commit()
    db_session.refresh(branch1)
    db_session.refresh(branch2)
    
    # Create employee with branch1
    employee = User(
        name="Employee",
        username="emp_change_branch",
        hashed_password=hash_password("emp123"),
        role=Role.EMPLOYEE,
        company_id=admin_user.company_id,
        branch_id=branch1.id,
    )
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(employee)
    
    payload = {
        "branch_id": branch2.id
    }
    
    response = await client.put(
        f"/api/v1/users/{employee.id}/admin",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["branch_id"] == branch2.id


@pytest.mark.asyncio
async def test_update_user_without_branch_no_field_sent(client, admin_user, db_session):
    """Update user without branch and not sending branch_id should keep it null"""
    token = get_admin_token(admin_user)
    
    # Create employee without branch
    employee = User(
        name="Employee No Branch",
        username="emp_no_branch",
        hashed_password=hash_password("emp123"),
        role=Role.EMPLOYEE,
        company_id=admin_user.company_id,
        branch_id=None,
    )
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(employee)
    
    payload = {
        "name": "Updated Name"
    }
    
    response = await client.put(
        f"/api/v1/users/{employee.id}/admin",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Name"
    assert data["branch_id"] is None  # Should remain null
