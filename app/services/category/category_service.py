from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.category import Category
from app.db.models.user import User, Role
from app.repositories.category_repository import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryUpdate


class CategoryService:
    """Business logic service for categories"""

    @staticmethod
    def create_category(
        db: Session,
        category_data: CategoryCreate,
        current_user: User
    ) -> Category:
        """
        Create a new category. Only MANAGER and ADMIN can create categories.
        Validations:
        - User must be MANAGER or ADMIN
        - Category belongs to user's company
        """
        if current_user.role not in (Role.MANAGER, Role.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="INSUFFICIENT_ROLE"
            )

        category = Category(
            name=category_data.name,
            color=category_data.color,
            company_id=current_user.company_id
        )

        CategoryRepository.create(db, category)
        CategoryRepository.commit(db)
        return category

    @staticmethod
    def get_category(
        db: Session,
        category_id: int,
        current_user: User
    ) -> Category:
        """
        Get a category. All users can view categories from their company.
        """
        category = CategoryRepository.get_by_id(db, category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="CATEGORY_NOT_FOUND"
            )

        # Verify category belongs to user's company
        if category.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CATEGORY_NOT_FOUND"
            )

        return category

    @staticmethod
    def update_category(
        db: Session,
        category_id: int,
        category_data: CategoryUpdate,
        current_user: User
    ) -> Category:
        """
        Update a category. Only MANAGER and ADMIN can update categories.
        Validations:
        - User must be MANAGER or ADMIN
        - Category must belong to user's company
        """
        if current_user.role not in (Role.MANAGER, Role.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="INSUFFICIENT_ROLE"
            )

        category = CategoryRepository.get_by_id(db, category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="CATEGORY_NOT_FOUND"
            )

        if category.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CATEGORY_NOT_FOUND"
            )

        # Update only provided fields
        if category_data.name is not None:
            category.name = category_data.name
        if category_data.color is not None:
            category.color = category_data.color

        CategoryRepository.update(db, category)
        CategoryRepository.commit(db)
        return category

    @staticmethod
    def delete_category(
        db: Session,
        category_id: int,
        current_user: User
    ) -> None:
        """
        Delete a category. Only ADMIN can delete categories.
        Validations:
        - User must be ADMIN
        - Category must belong to user's company
        """
        if current_user.role != Role.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="INSUFFICIENT_ROLE"
            )

        category = CategoryRepository.get_by_id(db, category_id)
        if not category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="CATEGORY_NOT_FOUND"
            )

        if category.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CATEGORY_NOT_FOUND"
            )

        CategoryRepository.delete(db, category)
        CategoryRepository.commit(db)
