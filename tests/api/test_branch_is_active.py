import pytest
from httpx import AsyncClient
from app.core.security import hash_password, create_access_token
from app.db.models.user import Role, User
from app.db.models.company import Company
from app.db.models.branch import Branch


@pytest.fixture
def admin_user(db_session):
    """Create an active admin user for tests"""
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
        is_active=True,
        company_id=company.id,
        branch_id=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_admin(db_session, admin_user):
    """Create an inactive admin user in the same company"""
    user = User(
        name="Inactive Admin",
        username="inactive_admin",
        hashed_password=hash_password("inactive_admin123"),
        role=Role.ADMIN,
        is_active=False,
        company_id=admin_user.company_id,
        branch_id=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def active_branch(db_session, admin_user):
    """Create an active branch"""
    branch = Branch(
        name="Main Branch",
        address="123 Main St",
        is_active=True,
        company_id=admin_user.company_id,
    )
    db_session.add(branch)
    db_session.commit()
    db_session.refresh(branch)
    return branch


@pytest.fixture
def branch_with_employee(db_session, admin_user, active_branch):
    """Create a branch with an assigned employee"""
    employee = User(
        name="Employee",
        username="employee",
        hashed_password=hash_password("emp123"),
        role=Role.EMPLOYEE,
        is_active=True,
        company_id=admin_user.company_id,
        branch_id=active_branch.id,
    )
    db_session.add(employee)
    db_session.commit()
    db_session.refresh(employee)
    return active_branch


class TestBranchActiveStatus:
    """Tests for is_active field validation in branches"""

    @pytest.mark.asyncio
    async def test_new_branch_created_as_active(self, client: AsyncClient, admin_user):
        """Test that new branches are created with is_active=True"""
        token = create_access_token({
            "sub": admin_user.username,
            "user_id": admin_user.id,
            "role": admin_user.role.value,
            "company_id": admin_user.company_id,
            "branch_id": admin_user.branch_id,
        })

        response = await client.post(
            "/api/v1/branches",
            json={
                "name": "New Branch",
                "address": "456 New St",
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["is_active"] is True
        assert data["name"] == "New Branch"

    @pytest.mark.asyncio
    async def test_inactive_admin_cannot_create_branch(self, client: AsyncClient, inactive_admin):
        """Test that inactive admins cannot create branches"""
        token = create_access_token({
            "sub": inactive_admin.username,
            "user_id": inactive_admin.id,
            "role": inactive_admin.role.value,
            "company_id": inactive_admin.company_id,
            "branch_id": inactive_admin.branch_id,
        })

        response = await client.post(
            "/api/v1/branches",
            json={
                "name": "Branch by Inactive Admin",
                "address": "789 Inactive St",
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_admin_cannot_update_branch(self, client: AsyncClient, inactive_admin, active_branch):
        """Test that inactive admins cannot update branches"""
        token = create_access_token({
            "sub": inactive_admin.username,
            "user_id": inactive_admin.id,
            "role": inactive_admin.role.value,
            "company_id": inactive_admin.company_id,
            "branch_id": inactive_admin.branch_id,
        })

        response = await client.put(
            f"/api/v1/branches/{active_branch.id}",
            json={"name": "Updated Name"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_admin_cannot_delete_branch(self, client: AsyncClient, inactive_admin, active_branch):
        """Test that inactive admins cannot delete branches"""
        token = create_access_token({
            "sub": inactive_admin.username,
            "user_id": inactive_admin.id,
            "role": inactive_admin.role.value,
            "company_id": inactive_admin.company_id,
            "branch_id": inactive_admin.branch_id,
        })

        response = await client.delete(
            f"/api/v1/branches/{active_branch.id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_deactivate_branch_without_users(self, client: AsyncClient, admin_user, active_branch):
        """Test that a branch without users can be deactivated"""
        token = create_access_token({
            "sub": admin_user.username,
            "user_id": admin_user.id,
            "role": admin_user.role.value,
            "company_id": admin_user.company_id,
            "branch_id": admin_user.branch_id,
        })

        response = await client.put(
            f"/api/v1/branches/{active_branch.id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    @pytest.mark.asyncio
    async def test_cannot_deactivate_branch_with_users(self, client: AsyncClient, admin_user, branch_with_employee):
        """Test that a branch with active users cannot be deactivated"""
        token = create_access_token({
            "sub": admin_user.username,
            "user_id": admin_user.id,
            "role": admin_user.role.value,
            "company_id": admin_user.company_id,
            "branch_id": admin_user.branch_id,
        })

        response = await client.put(
            f"/api/v1/branches/{branch_with_employee.id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "CANNOT_DEACTIVATE_BRANCH_WITH_USERS"

    @pytest.mark.asyncio
    async def test_can_deactivate_branch_when_user_removed(self, client: AsyncClient, admin_user, db_session, branch_with_employee):
        """Test that branch can be deactivated after removing all users"""
        token = create_access_token({
            "sub": admin_user.username,
            "user_id": admin_user.id,
            "role": admin_user.role.value,
            "company_id": admin_user.company_id,
            "branch_id": admin_user.branch_id,
        })

        # First, assign the employee elsewhere (remove from branch)
        employee = db_session.query(User).filter_by(username="employee").first()
        employee.branch_id = None
        db_session.commit()

        # Now deactivate the branch
        response = await client.put(
            f"/api/v1/branches/{branch_with_employee.id}",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    @pytest.mark.asyncio
    async def test_reactivate_branch(self, client: AsyncClient, admin_user, db_session, active_branch):
        """Test that a deactivated branch can be reactivated"""
        # First deactivate the branch
        active_branch.is_active = False
        db_session.commit()

        token = create_access_token({
            "sub": admin_user.username,
            "user_id": admin_user.id,
            "role": admin_user.role.value,
            "company_id": admin_user.company_id,
            "branch_id": admin_user.branch_id,
        })

        response = await client.put(
            f"/api/v1/branches/{active_branch.id}",
            json={"is_active": True},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_get_branches_includes_is_active_status(self, client: AsyncClient, admin_user, active_branch, db_session):
        """Test that get_branches_by_company returns is_active status"""
        # Create an inactive branch
        inactive_branch = Branch(
            name="Inactive Branch",
            address="999 Inactive St",
            is_active=False,
            company_id=admin_user.company_id,
        )
        db_session.add(inactive_branch)
        db_session.commit()

        token = create_access_token({
            "sub": admin_user.username,
            "user_id": admin_user.id,
            "role": admin_user.role.value,
            "company_id": admin_user.company_id,
            "branch_id": admin_user.branch_id,
        })

        response = await client.get(
            "/api/v1/branches",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        branches = response.json()
        assert len(branches) == 2

        # Check both active and inactive statuses are present
        statuses = [b["is_active"] for b in branches]
        assert True in statuses  # active branch
        assert False in statuses  # inactive branch

    @pytest.mark.asyncio
    async def test_get_branch_by_id_includes_is_active(self, client: AsyncClient, admin_user, active_branch):
        """Test that get_branch endpoint returns is_active status"""
        token = create_access_token({
            "sub": admin_user.username,
            "user_id": admin_user.id,
            "role": admin_user.role.value,
            "company_id": admin_user.company_id,
            "branch_id": admin_user.branch_id,
        })

        response = await client.get(
            f"/api/v1/branches/{active_branch.id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True
        assert data["id"] == active_branch.id
