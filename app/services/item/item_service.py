from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from pathlib import Path
from decimal import Decimal
import math

from app.db.models.item import Item, Unit
from app.db.models.user import User, Role
from app.db.models.category import Category
from app.repositories.item_repository import ItemRepository
from app.repositories.category_repository import CategoryRepository
from app.repositories.branch_repository import BranchRepository
from app.repositories.stock_movement_repository import StockMovementRepository
from app.schemas.item import ItemCreate, ItemUpdate, ItemWithStock, BranchStock
from app.schemas.common import PaginatedResponse
from app.core.file_handler import ItemImageHandler
from app.services.user.user_service import UserService


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
        UserService.validate_user_active(current_user)
        
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
        UserService.validate_user_active(current_user)
        
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
        UserService.validate_user_active(current_user)
        
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
        UserService.validate_user_active(current_user)
        
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
        UserService.validate_user_active(current_user)
        
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
        UserService.validate_user_active(current_user)
        
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

    @staticmethod
    def list_items(
        db: Session,
        current_user: User,
        page: int = 1,
        page_size: int = 20,
        is_active: Optional[bool] = None,
        category_id: Optional[int] = None,
        unit: Optional[str] = None,
        search: Optional[str] = None,
        order_by: str = "created_at",
        order_desc: bool = True
    ) -> PaginatedResponse[ItemWithStock]:
        """
        List items with filters, search, pagination, sorting and stock calculation.
        
        Filters:
        - is_active: Filter by active status (EMPLOYEE users are always forced to active items)
        - category_id: Filter by category
        - unit: Filter by unit of measure
        
        Search:
        - search: Search in name, sku, and brand (case-insensitive, partial match)
        
        Ordering:
        - order_by: Field to order by (sku, name, created_at, price, stock)
        - order_desc: True for descending, False for ascending
        
        Returns paginated response with items including stock per branch.
        Only active users from the same company can access.
        """
        UserService.validate_user_active(current_user)

        # Convert unit string to Unit enum if provided
        unit_enum = None
        if unit:
            try:
                unit_enum = Unit(unit)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="INVALID_UNIT"
                )

        # EMPLOYEE users always see only active items
        effective_is_active = is_active
        if current_user.role == Role.EMPLOYEE:
            effective_is_active = True

        # Validate category belongs to user's company if provided
        if category_id is not None:
            category = CategoryRepository.get_by_id_and_company(
                db, category_id, current_user.company_id
            )
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="CATEGORY_NOT_FOUND"
                )

        # Get all branches for the company
        branches = BranchRepository.get_by_company_id(db, current_user.company_id)
        branch_ids = [branch.id for branch in branches]

        # For stock ordering, we need to fetch all items first, then sort in memory
        # For other orderings, we can use database sorting
        if order_by == "stock":
            # Get all items without pagination for stock sorting
            items, total_count = ItemRepository.list_items_with_filters(
                db=db,
                company_id=current_user.company_id,
                page=1,
                page_size=10000,  # Large number to get all items
                is_active=effective_is_active,
                category_id=category_id,
                unit=unit_enum,
                search=search,
                order_by="created_at",  # Default ordering
                order_desc=True
            )
        else:
            # Get items with database-level sorting and pagination
            items, total_count = ItemRepository.list_items_with_filters(
                db=db,
                company_id=current_user.company_id,
                page=page,
                page_size=page_size,
                is_active=effective_is_active,
                category_id=category_id,
                unit=unit_enum,
                search=search,
                order_by=order_by,
                order_desc=order_desc
            )

        # Get stock for all items across all branches
        item_ids = [item.id for item in items]
        stock_dict = {}
        if item_ids and branch_ids:
            stock_dict = StockMovementRepository.get_stock_by_items_and_branches(
                db, item_ids, branch_ids
            )

        # Build response with stock information
        items_with_stock = []
        item_total_stock: dict[int, Decimal] = {}
        for item in items:
            # Calculate stock by branch for this item
            stock_by_branch = []
            total_stock = Decimal("0.000")
            for branch in branches:
                stock = stock_dict.get((item.id, branch.id), Decimal("0.000"))
                total_stock += stock
                stock_by_branch.append(BranchStock(
                    branch_id=branch.id,
                    branch_name=branch.name,
                    stock=stock
                ))

            item_with_stock = ItemWithStock(
                id=item.id,
                name=item.name,
                sku=item.sku,
                unit=item.unit.value,
                created_at=item.created_at,
                is_active=item.is_active,
                description=item.description,
                price=item.price,
                brand=item.brand,
                image_url=item.image_url,
                company_id=item.company_id,
                stock_by_branch=stock_by_branch
            )
            items_with_stock.append(item_with_stock)
            item_total_stock[item.id] = total_stock

        # If ordering by stock, sort in memory and apply pagination
        if order_by == "stock":
            items_with_stock.sort(
                key=lambda item_data: item_total_stock.get(item_data.id, Decimal("0.000")),
                reverse=order_desc
            )
            # Apply pagination
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            items_with_stock = items_with_stock[start_idx:end_idx]

        # Calculate total pages
        total_pages = math.ceil(total_count / page_size) if total_count > 0 else 0

        return PaginatedResponse(
            data=items_with_stock,
            total=total_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
