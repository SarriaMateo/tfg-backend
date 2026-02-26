from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pathlib import Path

from app.db.models.item import Item, Unit
from app.db.models.user import User, Role
from app.db.models.category import Category
from app.repositories.item_repository import ItemRepository
from app.repositories.category_repository import CategoryRepository
from app.schemas.item import ItemCreate, ItemUpdate
from app.core.file_handler import ItemImageHandler


class ItemService:
    """Business logic service for items"""

    @staticmethod
    def create_item(
        db: Session,
        item_data: ItemCreate,
        current_user: User,
        image_file: Optional[bytes] = None,
        image_filename: Optional[str] = None
    ) -> Item:
        """
        Create a new item. Only MANAGER and ADMIN can create items.
        Validations:
        - User must be MANAGER or ADMIN
        - SKU must be unique within the company
        """
        if current_user.role not in (Role.MANAGER, Role.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="INSUFFICIENT_ROLE"
            )

        # Verify SKU is unique within the company
        existing_item = ItemRepository.get_by_sku_and_company(
            db, item_data.sku, current_user.company_id
        )
        if existing_item:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="SKU_ALREADY_EXISTS"
            )

        # Handle image upload if provided
        image_url = None
        if image_file and image_filename:
            image_url = ItemImageHandler.save_image(image_file, image_filename, current_user.company_id)

        item = Item(
            name=item_data.name,
            sku=item_data.sku,
            unit=Unit(item_data.unit.value),
            description=item_data.description,
            price=item_data.price,
            brand=item_data.brand,
            image_url=image_url,
            company_id=current_user.company_id
        )

        ItemRepository.create(db, item)
        ItemRepository.commit(db)
        return item

    @staticmethod
    def get_item(
        db: Session,
        item_id: int,
        current_user: User
    ) -> Item:
        """
        Get an item. All users can view items from their company.
        """
        item = ItemRepository.get_by_id(db, item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ITEM_NOT_FOUND"
            )

        # Verify item belongs to user's company
        if item.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ITEM_NOT_FOUND"
            )

        return item

    @staticmethod
    def update_item(
        db: Session,
        item_id: int,
        item_data: ItemUpdate,
        current_user: User,
        image_file: Optional[bytes] = None,
        image_filename: Optional[str] = None,
        delete_image: bool = False
    ) -> Item:
        """
        Update an item. Only MANAGER and ADMIN can update items.
        Validations:
        - User must be MANAGER or ADMIN
        - Item must belong to user's company
        - If SKU is changed, it must remain unique within the company
        """
        if current_user.role not in (Role.MANAGER, Role.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="INSUFFICIENT_ROLE"
            )

        item = ItemRepository.get_by_id(db, item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ITEM_NOT_FOUND"
            )

        if item.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ITEM_NOT_FOUND"
            )

        # Check which fields were explicitly sent
        sent_fields = item_data.model_dump(exclude_unset=True)

        # Validate SKU uniqueness if it's being changed
        if item_data.sku is not None and item_data.sku != item.sku:
            existing_item = ItemRepository.get_by_sku_and_company(
                db, item_data.sku, current_user.company_id
            )
            if existing_item:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="SKU_ALREADY_EXISTS"
                )

        # Handle image update if new image is provided, or delete if flag is set
        if image_file and image_filename:
            # Delete old image if it exists
            if item.image_url:
                ItemImageHandler.delete_image(item.image_url)
            # Save new image
            item.image_url = ItemImageHandler.save_image(image_file, image_filename, current_user.company_id)
        elif delete_image:
            # Delete image if flag is set
            if item.image_url:
                ItemImageHandler.delete_image(item.image_url)
            item.image_url = None

        # Update only provided fields
        if item_data.name is not None:
            item.name = item_data.name
        if item_data.sku is not None:
            item.sku = item_data.sku
        if item_data.unit is not None:
            item.unit = Unit(item_data.unit.value)
        
        # Update optional fields only if explicitly sent (allows deletion by sending null)
        if "description" in sent_fields:
            item.description = item_data.description
        if "price" in sent_fields:
            item.price = item_data.price
        if "brand" in sent_fields:
            item.brand = item_data.brand
        
        if item_data.is_active is not None:
            item.is_active = item_data.is_active

        ItemRepository.update(db, item)
        ItemRepository.commit(db)
        return item

    @staticmethod
    def delete_item(
        db: Session,
        item_id: int,
        current_user: User
    ) -> None:
        """
        Delete an item. Only ADMIN can delete items.
        Validations:
        - User must be ADMIN
        - Item must belong to user's company
        """
        if current_user.role != Role.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="INSUFFICIENT_ROLE"
            )

        item = ItemRepository.get_by_id(db, item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ITEM_NOT_FOUND"
            )

        if item.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ITEM_NOT_FOUND"
            )

        # Delete image if it exists
        if item.image_url:
            ItemImageHandler.delete_image(item.image_url)

        ItemRepository.delete(db, item)
        ItemRepository.commit(db)

    @staticmethod
    def assign_categories(
        db: Session,
        item_id: int,
        category_ids: list[int],
        current_user: User
    ) -> Item:
        """
        Assign categories to an item. Only MANAGER and ADMIN can assign categories.
        
        Validations:
        - User must be MANAGER or ADMIN
        - Item must belong to user's company
        - All categories must belong to the same company as the item
        
        If category_ids is empty, all categories will be removed from the item.
        """
        if current_user.role not in (Role.MANAGER, Role.ADMIN):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="INSUFFICIENT_ROLE"
            )

        item = ItemRepository.get_by_id(db, item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ITEM_NOT_FOUND"
            )

        if item.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="ITEM_NOT_FOUND"
            )

        # Get all categories and verify they belong to the same company
        # If category_ids is empty, categories will be empty list (removes all)
        categories = []
        for category_id in category_ids:
            category = CategoryRepository.get_by_id_and_company(
                db, category_id, current_user.company_id
            )
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="CATEGORY_NOT_FOUND"
                )
            categories.append(category)

        # Assign/replace categories (empty list removes all)
        item.categories = categories

        ItemRepository.update(db, item)
        ItemRepository.commit(db)
        return item
    @staticmethod
    def get_item_image(
        db: Session,
        item_id: int,
        current_user: User
    ) -> tuple[Path, str]:
        """
        Get image file path for an item with security validation.
        Returns a tuple of (file_path: Path, media_type: str)
        
        Validations:
        - User must be authenticated
        - Item must belong to user's company
        - Item must have an image
        - Image file must exist on filesystem
        """
        # Verify user has access to this item (must be from same company)
        item = ItemService.get_item(db, item_id, current_user)
        
        # Check if item has an image
        if not item.image_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="IMAGE_NOT_FOUND"
            )
        
        # Get absolute path
        image_path = ItemImageHandler.get_absolute_path(item.image_url)
        
        # Verify file exists
        if not image_path or not image_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="IMAGE_NOT_FOUND"
            )
        
        # Determine media type based on file extension
        import mimetypes
        media_type, _ = mimetypes.guess_type(str(image_path))
        if not media_type:
            media_type = "application/octet-stream"
        
        return image_path, media_type