import pytest
from unittest.mock import Mock, MagicMock, patch
from fastapi import HTTPException
from decimal import Decimal

from app.db.models.item import Item, Unit
from app.db.models.user import User, Role
from app.db.models.category import Category
from app.schemas.item import ItemCreate, ItemUpdate, ItemUnit
from app.services.item.item_service import ItemService


@pytest.fixture
def mock_db():
    """Mock database session"""
    return Mock()


@pytest.fixture
def admin_user():
    """Create an admin user for testing"""
    user = Mock(spec=User)
    user.id = 1
    user.company_id = 1
    user.role = Role.ADMIN
    return user


@pytest.fixture
def manager_user():
    """Create a manager user for testing"""
    user = Mock(spec=User)
    user.id = 2
    user.company_id = 1
    user.role = Role.MANAGER
    return user


@pytest.fixture
def employee_user():
    """Create an employee user for testing"""
    user = Mock(spec=User)
    user.id = 3
    user.company_id = 1
    user.role = Role.EMPLOYEE
    return user


@pytest.fixture
def other_company_user():
    """Create a user from a different company"""
    user = Mock(spec=User)
    user.id = 4
    user.company_id = 2
    user.role = Role.ADMIN
    return user


class TestItemServiceCreate:
    """Tests for ItemService.create_item"""

    @patch("app.services.item.item_service.ItemRepository")
    def test_create_item_admin_success(self, mock_repo, mock_db, admin_user):
        """Admin can successfully create an item"""
        # Setup
        item_data = ItemCreate(
            name="Test Item",
            sku="SKU001",
            unit=ItemUnit.UNIT,
            price=Decimal("99.99")
        )
        mock_repo.get_by_sku_and_company.return_value = None

        # Execute
        result = ItemService.create_item(mock_db, item_data, admin_user)

        # Assert
        assert result is not None
        assert result.name == "Test Item"
        assert result.sku == "SKU001"
        assert result.company_id == admin_user.company_id
        mock_repo.create.assert_called_once()
        mock_repo.commit.assert_called_once()

    @patch("app.services.item.item_service.ItemRepository")
    def test_create_item_manager_success(self, mock_repo, mock_db, manager_user):
        """Manager can successfully create an item"""
        item_data = ItemCreate(
            name="Test Item",
            sku="SKU001",
            unit=ItemUnit.KILOGRAM
        )
        mock_repo.get_by_sku_and_company.return_value = None

        result = ItemService.create_item(mock_db, item_data, manager_user)

        assert result is not None
        assert result.company_id == manager_user.company_id
        mock_repo.create.assert_called_once()

    @patch("app.services.item.item_service.ItemRepository")
    def test_create_item_employee_forbidden(self, mock_repo, mock_db, employee_user):
        """Employee cannot create an item"""
        item_data = ItemCreate(
            name="Test Item",
            sku="SKU001",
            unit=ItemUnit.UNIT
        )

        with pytest.raises(HTTPException) as exc_info:
            ItemService.create_item(mock_db, item_data, employee_user)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "INSUFFICIENT_ROLE"

    @patch("app.services.item.item_service.ItemRepository")
    def test_create_item_duplicate_sku(self, mock_repo, mock_db, admin_user):
        """Creating item with duplicate SKU fails"""
        item_data = ItemCreate(
            name="Test Item",
            sku="SKU001",
            unit=ItemUnit.UNIT
        )
        # Simulate existing item with same SKU
        mock_repo.get_by_sku_and_company.return_value = Mock(spec=Item)

        with pytest.raises(HTTPException) as exc_info:
            ItemService.create_item(mock_db, item_data, admin_user)

        assert exc_info.value.status_code == 409
        assert exc_info.value.detail == "SKU_ALREADY_EXISTS"


class TestItemServiceGet:
    """Tests for ItemService.get_item"""

    @patch("app.services.item.item_service.ItemRepository")
    def test_get_item_success(self, mock_repo, mock_db, admin_user):
        """Successfully retrieve an item"""
        item = Mock(spec=Item)
        item.id = 1
        item.company_id = admin_user.company_id
        mock_repo.get_by_id.return_value = item

        result = ItemService.get_item(mock_db, 1, admin_user)

        assert result.id == 1
        assert result.company_id == admin_user.company_id

    @patch("app.services.item.item_service.ItemRepository")
    def test_get_item_not_found(self, mock_repo, mock_db, admin_user):
        """Getting non-existent item fails"""
        mock_repo.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            ItemService.get_item(mock_db, 999, admin_user)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "ITEM_NOT_FOUND"

    @patch("app.services.item.item_service.ItemRepository")
    def test_get_item_other_company(self, mock_repo, mock_db, admin_user, other_company_user):
        """Cannot access item from other company"""
        item = Mock(spec=Item)
        item.id = 1
        item.company_id = other_company_user.company_id
        mock_repo.get_by_id.return_value = item

        with pytest.raises(HTTPException) as exc_info:
            ItemService.get_item(mock_db, 1, admin_user)

        assert exc_info.value.status_code == 403


class TestItemServiceUpdate:
    """Tests for ItemService.update_item"""

    @patch("app.services.item.item_service.ItemRepository")
    def test_update_item_admin_success(self, mock_repo, mock_db, admin_user):
        """Admin can successfully update an item"""
        item = Mock(spec=Item)
        item.id = 1
        item.sku = "SKU001"
        item.company_id = admin_user.company_id
        item.image_url = None
        mock_repo.get_by_id.return_value = item
        mock_repo.get_by_sku_and_company.return_value = None

        item_data = ItemUpdate(name="Updated Item", price=Decimal("199.99"))

        result = ItemService.update_item(mock_db, 1, item_data, admin_user)

        assert result is not None
        mock_repo.update.assert_called_once()
        mock_repo.commit.assert_called_once()

    @patch("app.services.item.item_service.ItemRepository")
    def test_update_item_employee_forbidden(self, mock_repo, mock_db, employee_user):
        """Employee cannot update an item"""
        item_data = ItemUpdate(name="Updated Item")

        with pytest.raises(HTTPException) as exc_info:
            ItemService.update_item(mock_db, 1, item_data, employee_user)

        assert exc_info.value.status_code == 403

    @patch("app.services.item.item_service.ItemRepository")
    def test_update_item_duplicate_sku(self, mock_repo, mock_db, admin_user):
        """Updating to existing SKU fails"""
        item = Mock(spec=Item)
        item.id = 1
        item.sku = "SKU001"
        item.company_id = admin_user.company_id
        item.image_url = None
        mock_repo.get_by_id.return_value = item

        # Another item has the new SKU
        other_item = Mock(spec=Item)
        mock_repo.get_by_sku_and_company.return_value = other_item

        item_data = ItemUpdate(sku="SKU002")

        with pytest.raises(HTTPException) as exc_info:
            ItemService.update_item(mock_db, 1, item_data, admin_user)

        assert exc_info.value.status_code == 409

    @patch("app.services.item.item_service.ItemRepository")
    def test_update_item_not_found(self, mock_repo, mock_db, admin_user):
        """Updating non-existent item fails"""
        mock_repo.get_by_id.return_value = None
        item_data = ItemUpdate(name="Updated Item")

        with pytest.raises(HTTPException) as exc_info:
            ItemService.update_item(mock_db, 999, item_data, admin_user)

        assert exc_info.value.status_code == 404

    @patch("app.services.item.item_service.ItemRepository")
    def test_update_item_other_company(self, mock_repo, mock_db, admin_user, other_company_user):
        """Cannot update item from other company"""
        item = Mock(spec=Item)
        item.id = 1
        item.company_id = other_company_user.company_id
        mock_repo.get_by_id.return_value = item

        item_data = ItemUpdate(name="Updated Item")

        with pytest.raises(HTTPException) as exc_info:
            ItemService.update_item(mock_db, 1, item_data, admin_user)

        assert exc_info.value.status_code == 403


class TestItemServiceDelete:
    """Tests for ItemService.delete_item"""

    @patch("app.services.item.item_service.ItemRepository")
    def test_delete_item_admin_success(self, mock_repo, mock_db, admin_user):
        """Admin can successfully delete an item"""
        item = Mock(spec=Item)
        item.id = 1
        item.company_id = admin_user.company_id
        item.image_url = None
        mock_repo.get_by_id.return_value = item

        ItemService.delete_item(mock_db, 1, admin_user)

        mock_repo.delete.assert_called_once()
        mock_repo.commit.assert_called_once()

    @patch("app.services.item.item_service.ItemRepository")
    def test_delete_item_manager_forbidden(self, mock_repo, mock_db, manager_user):
        """Manager cannot delete an item"""
        with pytest.raises(HTTPException) as exc_info:
            ItemService.delete_item(mock_db, 1, manager_user)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "INSUFFICIENT_ROLE"

    @patch("app.services.item.item_service.ItemRepository")
    def test_delete_item_not_found(self, mock_repo, mock_db, admin_user):
        """Deleting non-existent item fails"""
        mock_repo.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            ItemService.delete_item(mock_db, 999, admin_user)

        assert exc_info.value.status_code == 404

    @patch("app.services.item.item_service.ItemRepository")
    def test_delete_item_other_company(self, mock_repo, mock_db, admin_user, other_company_user):
        """Cannot delete item from other company"""
        item = Mock(spec=Item)
        item.id = 1
        item.company_id = other_company_user.company_id
        item.image_url = None
        mock_repo.get_by_id.return_value = item

        with pytest.raises(HTTPException) as exc_info:
            ItemService.delete_item(mock_db, 1, admin_user)

        assert exc_info.value.status_code == 403


class TestItemServiceAssignCategories:
    """Tests for ItemService.assign_categories"""

    @patch("app.services.item.item_service.CategoryRepository")
    @patch("app.services.item.item_service.ItemRepository")
    def test_assign_categories_success(self, mock_item_repo, mock_cat_repo, mock_db, admin_user):
        """Manager can successfully assign categories to item"""
        item = Mock(spec=Item)
        item.id = 1
        item.company_id = admin_user.company_id
        mock_item_repo.get_by_id.return_value = item

        category = Mock(spec=Category)
        category.id = 1
        mock_cat_repo.get_by_id_and_company.return_value = category

        ItemService.assign_categories(mock_db, 1, [1], admin_user)

        assert item.categories == [category]
        mock_item_repo.update.assert_called_once()

    @patch("app.services.item.item_service.ItemRepository")
    def test_assign_categories_employee_forbidden(self, mock_repo, mock_db, employee_user):
        """Employee cannot assign categories"""
        with pytest.raises(HTTPException) as exc_info:
            ItemService.assign_categories(mock_db, 1, [1], employee_user)

        assert exc_info.value.status_code == 403

    @patch("app.services.item.item_service.ItemRepository")
    def test_assign_categories_item_not_found(self, mock_repo, mock_db, admin_user):
        """Assigning categories to non-existent item fails"""
        mock_repo.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            ItemService.assign_categories(mock_db, 999, [1], admin_user)

        assert exc_info.value.status_code == 404

    @patch("app.services.item.item_service.CategoryRepository")
    @patch("app.services.item.item_service.ItemRepository")
    def test_assign_categories_from_other_company(self, mock_item_repo, mock_cat_repo, mock_db, admin_user):
        """Cannot assign categories from different company"""
        item = Mock(spec=Item)
        item.id = 1
        item.company_id = admin_user.company_id
        mock_item_repo.get_by_id.return_value = item

        # Category from different company
        mock_cat_repo.get_by_id_and_company.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            ItemService.assign_categories(mock_db, 1, [999], admin_user)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "CATEGORY_NOT_FOUND"

    @patch("app.services.item.item_service.ItemRepository")
    def test_assign_categories_empty_list(self, mock_repo, mock_db, admin_user):
        """Empty list removes all categories from item"""
        item = Mock(spec=Item)
        item.id = 1
        item.company_id = admin_user.company_id
        item.categories = [Mock(spec=Category), Mock(spec=Category)]  # Has categories
        mock_repo.get_by_id.return_value = item

        ItemService.assign_categories(mock_db, 1, [], admin_user)

        # Categories should be empty
        assert item.categories == []
        mock_repo.update.assert_called_once()
