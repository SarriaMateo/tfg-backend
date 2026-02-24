import pytest
from unittest.mock import Mock, patch
from fastapi import HTTPException

from app.db.models.category import Category
from app.db.models.user import User, Role
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.category.category_service import CategoryService


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


class TestCategoryServiceCreate:
    """Tests for CategoryService.create_category"""

    @patch("app.services.category.category_service.CategoryRepository")
    def test_create_category_admin_success(self, mock_repo, mock_db, admin_user):
        """Admin can successfully create a category"""
        # Setup
        category_data = CategoryCreate(
            name="Electronics",
            color="#FF0000"
        )
        mock_repo.get_by_name_and_company.return_value = None

        # Execute
        result = CategoryService.create_category(mock_db, category_data, admin_user)

        # Assert
        assert result is not None
        assert result.name == "Electronics"
        assert result.color == "#FF0000"
        assert result.company_id == admin_user.company_id
        mock_repo.create.assert_called_once()
        mock_repo.commit.assert_called_once()

    @patch("app.services.category.category_service.CategoryRepository")
    def test_create_category_manager_success(self, mock_repo, mock_db, manager_user):
        """Manager can successfully create a category"""
        category_data = CategoryCreate(
            name="Books",
            color="#0000FF"
        )
        mock_repo.get_by_name_and_company.return_value = None

        result = CategoryService.create_category(mock_db, category_data, manager_user)

        assert result is not None
        assert result.company_id == manager_user.company_id
        mock_repo.create.assert_called_once()

    @patch("app.services.category.category_service.CategoryRepository")
    def test_create_category_employee_forbidden(self, mock_repo, mock_db, employee_user):
        """Employee cannot create a category"""
        category_data = CategoryCreate(
            name="Books",
            color="#0000FF"
        )

        with pytest.raises(HTTPException) as exc_info:
            CategoryService.create_category(mock_db, category_data, employee_user)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "INSUFFICIENT_ROLE"

    @patch("app.services.category.category_service.CategoryRepository")
    def test_create_category_duplicate_name(self, mock_repo, mock_db, admin_user):
        """Creating category with duplicate name is allowed (no DB uniqueness constraint in service)"""
        category_data = CategoryCreate(
            name="Electronics",
            color="#FF0000"
        )
        
        result = CategoryService.create_category(mock_db, category_data, admin_user)

        assert result is not None
        assert result.name == "Electronics"
        mock_repo.create.assert_called_once()


class TestCategoryServiceGetByCompany:
    """Tests for CategoryService.get_categories_by_company"""

    @pytest.fixture
    def mock_db(self):
        """Mock database session"""
        return Mock()

    @patch("app.services.category.category_service.CategoryRepository")
    def test_get_categories_by_company_success(self, mock_repo, mock_db, admin_user):
        """Get all categories for a company"""
        category1 = Mock(spec=Category)
        category1.id = 1
        category1.name = "Electronics"
        category2 = Mock(spec=Category)
        category2.id = 2
        category2.name = "Books"
        
        mock_repo.get_by_company_id.return_value = [category1, category2]

        result = CategoryService.get_categories_by_company(mock_db, admin_user)

        assert len(result) == 2
        assert result[0].name == "Electronics"
        assert result[1].name == "Books"
        mock_repo.get_by_company_id.assert_called_once_with(mock_db, admin_user.company_id)

    @patch("app.services.category.category_service.CategoryRepository")
    def test_get_categories_by_company_empty(self, mock_repo, mock_db, admin_user):
        """Get categories when company has none"""
        mock_repo.get_by_company_id.return_value = []

        result = CategoryService.get_categories_by_company(mock_db, admin_user)

        assert result == []
        mock_repo.get_by_company_id.assert_called_once_with(mock_db, admin_user.company_id)


class TestCategoryServiceGet:
    """Tests for CategoryService.get_category"""

    @patch("app.services.category.category_service.CategoryRepository")
    def test_get_category_success(self, mock_repo, mock_db, admin_user):
        """Successfully retrieve a category"""
        category = Mock(spec=Category)
        category.id = 1
        category.company_id = admin_user.company_id
        mock_repo.get_by_id.return_value = category

        result = CategoryService.get_category(mock_db, 1, admin_user)

        assert result.id == 1
        assert result.company_id == admin_user.company_id

    @patch("app.services.category.category_service.CategoryRepository")
    def test_get_category_not_found(self, mock_repo, mock_db, admin_user):
        """Getting non-existent category fails"""
        mock_repo.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            CategoryService.get_category(mock_db, 999, admin_user)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "CATEGORY_NOT_FOUND"

    @patch("app.services.category.category_service.CategoryRepository")
    def test_get_category_other_company(self, mock_repo, mock_db, admin_user, other_company_user):
        """Cannot access category from other company"""
        category = Mock(spec=Category)
        category.id = 1
        category.company_id = other_company_user.company_id
        mock_repo.get_by_id.return_value = category

        with pytest.raises(HTTPException) as exc_info:
            CategoryService.get_category(mock_db, 1, admin_user)

        assert exc_info.value.status_code == 403


class TestCategoryServiceUpdate:
    """Tests for CategoryService.update_category"""

    @patch("app.services.category.category_service.CategoryRepository")
    def test_update_category_admin_success(self, mock_repo, mock_db, admin_user):
        """Admin can successfully update a category"""
        category = Mock(spec=Category)
        category.id = 1
        category.name = "Electronics"
        category.company_id = admin_user.company_id
        mock_repo.get_by_id.return_value = category

        category_data = CategoryUpdate(name="Updated Category", color="#00FF00")

        result = CategoryService.update_category(mock_db, 1, category_data, admin_user)

        assert result is not None
        mock_repo.update.assert_called_once()
        mock_repo.commit.assert_called_once()

    @patch("app.services.category.category_service.CategoryRepository")
    def test_update_category_employee_forbidden(self, mock_repo, mock_db, employee_user):
        """Employee cannot update a category"""
        category_data = CategoryUpdate(name="Updated Category")

        with pytest.raises(HTTPException) as exc_info:
            CategoryService.update_category(mock_db, 1, category_data, employee_user)

        assert exc_info.value.status_code == 403

    @patch("app.services.category.category_service.CategoryRepository")
    def test_update_category_duplicate_name(self, mock_repo, mock_db, admin_user):
        """Updating category name is allowed (no duplicate check in service)"""
        category = Mock(spec=Category)
        category.id = 1
        category.name = "Electronics"
        category.company_id = admin_user.company_id
        mock_repo.get_by_id.return_value = category

        category_data = CategoryUpdate(name="Books")

        result = CategoryService.update_category(mock_db, 1, category_data, admin_user)

        assert result is not None
        mock_repo.update.assert_called_once()

    @patch("app.services.category.category_service.CategoryRepository")
    def test_update_category_not_found(self, mock_repo, mock_db, admin_user):
        """Updating non-existent category fails"""
        mock_repo.get_by_id.return_value = None
        category_data = CategoryUpdate(name="Updated Category")

        with pytest.raises(HTTPException) as exc_info:
            CategoryService.update_category(mock_db, 1, category_data, admin_user)

        assert exc_info.value.status_code == 404

    @patch("app.services.category.category_service.CategoryRepository")
    def test_update_category_partial(self, mock_repo, mock_db, admin_user):
        """Can update category with partial fields"""
        category = Mock(spec=Category)
        category.id = 1
        category.name = "Electronics"
        category.color = "#FF0000"
        category.company_id = admin_user.company_id
        mock_repo.get_by_id.return_value = category

        # Update only color, not name
        category_data = CategoryUpdate(color="#00FF00")

        result = CategoryService.update_category(mock_db, 1, category_data, admin_user)

        assert result is not None
        mock_repo.update.assert_called_once()


class TestCategoryServiceDelete:
    """Tests for CategoryService.delete_category"""

    @patch("app.services.category.category_service.CategoryRepository")
    def test_delete_category_admin_success(self, mock_repo, mock_db, admin_user):
        """Admin can successfully delete a category"""
        category = Mock(spec=Category)
        category.id = 1
        category.company_id = admin_user.company_id
        mock_repo.get_by_id.return_value = category

        CategoryService.delete_category(mock_db, 1, admin_user)

        mock_repo.delete.assert_called_once()
        mock_repo.commit.assert_called_once()

    @patch("app.services.category.category_service.CategoryRepository")
    def test_delete_category_manager_forbidden(self, mock_repo, mock_db, manager_user):
        """Manager cannot delete a category"""
        with pytest.raises(HTTPException) as exc_info:
            CategoryService.delete_category(mock_db, 1, manager_user)

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "INSUFFICIENT_ROLE"

    @patch("app.services.category.category_service.CategoryRepository")
    def test_delete_category_not_found(self, mock_repo, mock_db, admin_user):
        """Deleting non-existent category fails"""
        mock_repo.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            CategoryService.delete_category(mock_db, 999, admin_user)

        assert exc_info.value.status_code == 404

    @patch("app.services.category.category_service.CategoryRepository")
    def test_delete_category_other_company(self, mock_repo, mock_db, admin_user, other_company_user):
        """Cannot delete category from other company"""
        category = Mock(spec=Category)
        category.id = 1
        category.company_id = other_company_user.company_id
        mock_repo.get_by_id.return_value = category

        with pytest.raises(HTTPException) as exc_info:
            CategoryService.delete_category(mock_db, 1, admin_user)

        assert exc_info.value.status_code == 403
