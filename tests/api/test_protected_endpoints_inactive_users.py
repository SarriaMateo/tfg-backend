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
def manager_user(db_session, admin_user):
    """Create an active manager user"""
    user = User(
        name="Manager User",
        username="manager_user",
        hashed_password=hash_password("mgr123"),
        role=Role.MANAGER,
        is_active=True,
        company_id=admin_user.company_id,
        branch_id=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_admin(db_session, admin_user):
    """Create an inactive admin user"""
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
def inactive_manager(db_session, admin_user):
    """Create an inactive manager user"""
    user = User(
        name="Inactive Manager",
        username="inactive_manager",
        hashed_password=hash_password("inactive_mgr123"),
        role=Role.MANAGER,
        is_active=False,
        company_id=admin_user.company_id,
        branch_id=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_branch(db_session, admin_user):
    """Create a test branch"""
    branch = Branch(
        name="Test Branch",
        address="123 Test St",
        company_id=admin_user.company_id
    )
    db_session.add(branch)
    db_session.commit()
    db_session.refresh(branch)
    return branch


class TestInactiveUsersProtectedEndpoints:
    """Tests for is_active validation on branch, company, item, and category endpoints"""

    # BRANCH ENDPOINTS

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
                "name": "New Branch",
                "address": "456 New St"
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_user_cannot_get_branch(self, client: AsyncClient, inactive_manager, admin_user, test_branch):
        """Test that inactive users cannot get branches"""
        token = create_access_token({
            "sub": inactive_manager.username,
            "user_id": inactive_manager.id,
            "role": inactive_manager.role.value,
            "company_id": inactive_manager.company_id,
            "branch_id": inactive_manager.branch_id,
        })

        response = await client.get(
            f"/api/v1/branches/{test_branch.id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_user_cannot_list_branches(self, client: AsyncClient, inactive_manager):
        """Test that inactive users cannot list branches"""
        token = create_access_token({
            "sub": inactive_manager.username,
            "user_id": inactive_manager.id,
            "role": inactive_manager.role.value,
            "company_id": inactive_manager.company_id,
            "branch_id": inactive_manager.branch_id,
        })

        response = await client.get(
            "/api/v1/branches",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_admin_cannot_update_branch(self, client: AsyncClient, inactive_admin, test_branch):
        """Test that inactive admins cannot update branches"""
        token = create_access_token({
            "sub": inactive_admin.username,
            "user_id": inactive_admin.id,
            "role": inactive_admin.role.value,
            "company_id": inactive_admin.company_id,
            "branch_id": inactive_admin.branch_id,
        })

        response = await client.put(
            f"/api/v1/branches/{test_branch.id}",
            json={"name": "Updated Branch"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_admin_cannot_delete_branch(self, client: AsyncClient, inactive_admin, test_branch):
        """Test that inactive admins cannot delete branches"""
        token = create_access_token({
            "sub": inactive_admin.username,
            "user_id": inactive_admin.id,
            "role": inactive_admin.role.value,
            "company_id": inactive_admin.company_id,
            "branch_id": inactive_admin.branch_id,
        })

        response = await client.delete(
            f"/api/v1/branches/{test_branch.id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    # COMPANY ENDPOINTS

    @pytest.mark.asyncio
    async def test_inactive_user_cannot_get_company(self, client: AsyncClient, inactive_manager):
        """Test that inactive users cannot get company info"""
        token = create_access_token({
            "sub": inactive_manager.username,
            "user_id": inactive_manager.id,
            "role": inactive_manager.role.value,
            "company_id": inactive_manager.company_id,
            "branch_id": inactive_manager.branch_id,
        })

        response = await client.get(
            "/api/v1/company",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_admin_cannot_update_company(self, client: AsyncClient, inactive_admin):
        """Test that inactive admins cannot update company"""
        token = create_access_token({
            "sub": inactive_admin.username,
            "user_id": inactive_admin.id,
            "role": inactive_admin.role.value,
            "company_id": inactive_admin.company_id,
            "branch_id": inactive_admin.branch_id,
        })

        response = await client.put(
            "/api/v1/company",
            json={"name": "Updated Company"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    # ITEM ENDPOINTS

    @pytest.mark.asyncio
    async def test_inactive_manager_cannot_create_item(self, client: AsyncClient, inactive_manager):
        """Test that inactive managers cannot create items"""
        token = create_access_token({
            "sub": inactive_manager.username,
            "user_id": inactive_manager.id,
            "role": inactive_manager.role.value,
            "company_id": inactive_manager.company_id,
            "branch_id": inactive_manager.branch_id,
        })

        # Use FormData for file upload endpoint
        response = await client.post(
            "/api/v1/items",
            data={"name": "Test Item", "sku": "SKU123", "unit": "ud"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_user_cannot_get_item(self, client: AsyncClient, inactive_manager, db_session, admin_user):
        """Test that inactive users cannot get items"""
        from app.db.models.item import Item, Unit
        
        # Create an item
        item = Item(
            name="Test Item",
            sku="SKU123",
            unit=Unit.UNIT,
            company_id=admin_user.company_id
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        token = create_access_token({
            "sub": inactive_manager.username,
            "user_id": inactive_manager.id,
            "role": inactive_manager.role.value,
            "company_id": inactive_manager.company_id,
            "branch_id": inactive_manager.branch_id,
        })

        response = await client.get(
            f"/api/v1/items/{item.id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_manager_cannot_update_item(self, client: AsyncClient, inactive_manager, db_session, admin_user):
        """Test that inactive managers cannot update items"""
        from app.db.models.item import Item, Unit
        
        # Create an item
        item = Item(
            name="Test Item",
            sku="SKU123",
            unit=Unit.UNIT,
            company_id=admin_user.company_id
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        token = create_access_token({
            "sub": inactive_manager.username,
            "user_id": inactive_manager.id,
            "role": inactive_manager.role.value,
            "company_id": inactive_manager.company_id,
            "branch_id": inactive_manager.branch_id,
        })

        response = await client.put(
            f"/api/v1/items/{item.id}",
            json={"name": "Updated Item"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_admin_cannot_delete_item(self, client: AsyncClient, inactive_admin, db_session):
        """Test that inactive admins cannot delete items"""
        from app.db.models.item import Item, Unit
        
        # Create an item
        item = Item(
            name="Test Item",
            sku="SKU123",
            unit=Unit.UNIT,
            company_id=inactive_admin.company_id
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)

        token = create_access_token({
            "sub": inactive_admin.username,
            "user_id": inactive_admin.id,
            "role": inactive_admin.role.value,
            "company_id": inactive_admin.company_id,
            "branch_id": inactive_admin.branch_id,
        })

        response = await client.delete(
            f"/api/v1/items/{item.id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    # CATEGORY ENDPOINTS

    @pytest.mark.asyncio
    async def test_inactive_manager_cannot_create_category(self, client: AsyncClient, inactive_manager):
        """Test that inactive managers cannot create categories"""
        token = create_access_token({
            "sub": inactive_manager.username,
            "user_id": inactive_manager.id,
            "role": inactive_manager.role.value,
            "company_id": inactive_manager.company_id,
            "branch_id": inactive_manager.branch_id,
        })

        response = await client.post(
            "/api/v1/categories",
            json={
                "name": "Test Category",
                "color": "#FF0000"
            },
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_user_cannot_get_categories(self, client: AsyncClient, inactive_manager):
        """Test that inactive users cannot get categories"""
        token = create_access_token({
            "sub": inactive_manager.username,
            "user_id": inactive_manager.id,
            "role": inactive_manager.role.value,
            "company_id": inactive_manager.company_id,
            "branch_id": inactive_manager.branch_id,
        })

        response = await client.get(
            "/api/v1/categories",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_manager_cannot_update_category(self, client: AsyncClient, inactive_manager, db_session):
        """Test that inactive managers cannot update categories"""
        from app.db.models.category import Category
        
        # Create a category
        category = Category(
            name="Test Category",
            color="#FF0000",
            company_id=inactive_manager.company_id
        )
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)

        token = create_access_token({
            "sub": inactive_manager.username,
            "user_id": inactive_manager.id,
            "role": inactive_manager.role.value,
            "company_id": inactive_manager.company_id,
            "branch_id": inactive_manager.branch_id,
        })

        response = await client.put(
            f"/api/v1/categories/{category.id}",
            json={"name": "Updated Category"},
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"

    @pytest.mark.asyncio
    async def test_inactive_admin_cannot_delete_category(self, client: AsyncClient, inactive_admin, db_session):
        """Test that inactive admins cannot delete categories"""
        from app.db.models.category import Category
        
        # Create a category
        category = Category(
            name="Test Category",
            color="#FF0000",
            company_id=inactive_admin.company_id
        )
        db_session.add(category)
        db_session.commit()
        db_session.refresh(category)

        token = create_access_token({
            "sub": inactive_admin.username,
            "user_id": inactive_admin.id,
            "role": inactive_admin.role.value,
            "company_id": inactive_admin.company_id,
            "branch_id": inactive_admin.branch_id,
        })

        response = await client.delete(
            f"/api/v1/categories/{category.id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "USER_INACTIVE"
