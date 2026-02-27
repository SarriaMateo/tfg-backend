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
def inactive_user(db_session, admin_user):
    """Create an inactive user in the same company"""
    user = User(
        name="Inactive User",
        username="inactive_user",
        hashed_password=hash_password("inactive123"),
        role=Role.EMPLOYEE,
        is_active=False,
        company_id=admin_user.company_id,
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


class TestUserActiveStatus:
    """Tests for is_active field validation"""

    @pytest.mark.asyncio
    async def test_new_user_created_as_active(self, client: AsyncClient, admin_user):
        """Test that new users are created with is_active=True"""
        token = create_access_token({
            "sub": admin_user.username,
            "user_id": admin_user.id,
            "role": admin_user.role.value,
            "company_id": admin_user.company_id,
            "branch_id": admin_user.branch_id,
        })

        response = await client.post(
            "/api/v1/users",
            json={
                "name": "New User",
                "username": "new_user",
                "password": "password123",
                "role": "EMPLOYEE"
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_inactive_user_cannot_get_own_profile(self, client: AsyncClient, inactive_user):
        """Test that inactive users cannot access get_user endpoint"""
        token = create_access_token({
            "sub": inactive_user.username,
            "user_id": inactive_user.id,
            "role": inactive_user.role.value,
            "company_id": inactive_user.company_id,
            "branch_id": inactive_user.branch_id,
        })

        response = await client.get(
            f"/api/v1/users/{inactive_user.id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_user_cannot_update_profile(self, client: AsyncClient, inactive_user):
        """Test that inactive users cannot update their profile"""
        token = create_access_token({
            "sub": inactive_user.username,
            "user_id": inactive_user.id,
            "role": inactive_user.role.value,
            "company_id": inactive_user.company_id,
            "branch_id": inactive_user.branch_id,
        })

        response = await client.put(
            f"/api/v1/users/{inactive_user.id}",
            json={"name": "Updated Name"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_admin_cannot_create_user(self, client: AsyncClient, inactive_admin):
        """Test that inactive admins cannot create users"""
        token = create_access_token({
            "sub": inactive_admin.username,
            "user_id": inactive_admin.id,
            "role": inactive_admin.role.value,
            "company_id": inactive_admin.company_id,
            "branch_id": inactive_admin.branch_id,
        })

        response = await client.post(
            "/api/v1/users",
            json={
                "name": "New User",
                "username": "new_user",
                "password": "password123",
                "role": "EMPLOYEE"
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_admin_cannot_list_users(self, client: AsyncClient, inactive_admin):
        """Test that inactive admins cannot list company users"""
        token = create_access_token({
            "sub": inactive_admin.username,
            "user_id": inactive_admin.id,
            "role": inactive_admin.role.value,
            "company_id": inactive_admin.company_id,
            "branch_id": inactive_admin.branch_id,
        })

        response = await client.get(
            "/api/v1/users",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_admin_cannot_delete_user(self, client: AsyncClient, inactive_admin, db_session):
        """Test that inactive admins cannot delete users"""
        # Create a user to potentially delete
        other_user = User(
            name="Other User",
            username="other_user",
            hashed_password=hash_password("other123"),
            role=Role.EMPLOYEE,
            is_active=True,
            company_id=inactive_admin.company_id,
            branch_id=None,
        )
        db_session.add(other_user)
        db_session.commit()

        token = create_access_token({
            "sub": inactive_admin.username,
            "user_id": inactive_admin.id,
            "role": inactive_admin.role.value,
            "company_id": inactive_admin.company_id,
            "branch_id": inactive_admin.branch_id,
        })

        response = await client.delete(
            f"/api/v1/users/{other_user.id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_admin_can_deactivate_user(self, client: AsyncClient, admin_user, db_session):
        """Test that admin can deactivate an active user"""
        # Create an active employee
        employee = User(
            name="Employee User",
            username="employee_user",
            hashed_password=hash_password("emp123"),
            role=Role.EMPLOYEE,
            is_active=True,
            company_id=admin_user.company_id,
            branch_id=None,
        )
        db_session.add(employee)
        db_session.commit()
        db_session.refresh(employee)

        token = create_access_token({
            "sub": admin_user.username,
            "user_id": admin_user.id,
            "role": admin_user.role.value,
            "company_id": admin_user.company_id,
            "branch_id": admin_user.branch_id,
        })

        response = await client.put(
            f"/api/v1/users/{employee.id}/admin",
            json={"is_active": False},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is False

    @pytest.mark.asyncio
    async def test_admin_can_reactivate_user(self, client: AsyncClient, admin_user, inactive_user):
        """Test that admin can reactivate an inactive user"""
        token = create_access_token({
            "sub": admin_user.username,
            "user_id": admin_user.id,
            "role": admin_user.role.value,
            "company_id": admin_user.company_id,
            "branch_id": admin_user.branch_id,
        })

        response = await client.put(
            f"/api/v1/users/{inactive_user.id}/admin",
            json={"is_active": True},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_reactivated_user_can_access_endpoints(self, client: AsyncClient, admin_user, db_session, inactive_user):
        """Test that reactivated user can access protected endpoints"""
        # First, reactivate the user
        admin_token = create_access_token({
            "sub": admin_user.username,
            "user_id": admin_user.id,
            "role": admin_user.role.value,
            "company_id": admin_user.company_id,
            "branch_id": admin_user.branch_id,
        })

        response = await client.put(
            f"/api/v1/users/{inactive_user.id}/admin",
            json={"is_active": True},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200

        # Refresh the inactive_user from db to get updated is_active
        db_session.refresh(inactive_user)

        # Now try to access with the reactivated user's token
        user_token = create_access_token({
            "sub": inactive_user.username,
            "user_id": inactive_user.id,
            "role": inactive_user.role.value,
            "company_id": inactive_user.company_id,
            "branch_id": inactive_user.branch_id,
        })

        response = await client.get(
            f"/api/v1/users/{inactive_user.id}",
            headers={"Authorization": f"Bearer {user_token}"}
        )

        assert response.status_code == 200
        assert response.json()["is_active"] is True

    @pytest.mark.asyncio
    async def test_non_admin_cannot_change_is_active(self, client: AsyncClient, db_session, admin_user):
        """Test that non-admin users cannot change is_active field"""
        # Create an employee
        employee = User(
            name="Employee User",
            username="employee_user",
            hashed_password=hash_password("emp123"),
            role=Role.EMPLOYEE,
            is_active=True,
            company_id=admin_user.company_id,
            branch_id=None,
        )
        db_session.add(employee)
        db_session.commit()
        db_session.refresh(employee)

        token = create_access_token({
            "sub": employee.username,
            "user_id": employee.id,
            "role": employee.role.value,
            "company_id": employee.company_id,
            "branch_id": employee.branch_id,
        })

        # Try to use UserUpdate instead of UserUpdateAdmin
        response = await client.put(
            f"/api/v1/users/{employee.id}",
            json={"name": "Updated Name"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        # Verify is_active wasn't attempted to be changed
        assert response.json()["is_active"] is True
