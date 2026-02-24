from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.category import CategoryCreate, CategoryUpdate, CategoryResponse
from app.core.security import get_current_user, require_roles
from app.db.models.user import User
from app.services.category.category_service import CategoryService
from app.repositories.category_repository import CategoryRepository

router = APIRouter(prefix="/categories", tags=["categories"])


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED
)
def create_category(
    category_data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("MANAGER", "ADMIN"))
):
    """
    Create a new category. Only MANAGER and ADMIN can create categories.
    Company is extracted from the authenticated user.
    """
    new_category = CategoryService.create_category(db, category_data, current_user)
    CategoryRepository.commit(db)
    return new_category


@router.get(
    "",
    response_model=list[CategoryResponse],
    status_code=status.HTTP_200_OK
)
def get_company_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all categories in the user's company. All users can view all categories.
    """
    categories = CategoryService.get_categories_by_company(db, current_user)
    return categories


@router.get(
    "/{category_id}",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK
)
def get_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a category by ID. All users can view categories from their company.
    """
    category = CategoryService.get_category(db, category_id, current_user)
    return category


@router.put(
    "/{category_id}",
    response_model=CategoryResponse,
    status_code=status.HTTP_200_OK
)
def update_category(
    category_id: int,
    category_data: CategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("MANAGER", "ADMIN"))
):
    """
    Update a category. Only MANAGER and ADMIN can update categories.
    """
    updated_category = CategoryService.update_category(
        db, category_id, category_data, current_user
    )
    CategoryRepository.commit(db)
    return updated_category


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN"))
):
    """
    Delete a category. Only ADMIN can delete categories.
    """
    CategoryService.delete_category(db, category_id, current_user)
    CategoryRepository.commit(db)
    return None
