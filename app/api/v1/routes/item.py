from fastapi import APIRouter, Depends, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import Optional, Literal

from app.db.session import get_db
from app.schemas.item import ItemCreate, ItemUpdate, ItemResponse
from app.schemas.common import PaginatedResponse
from app.schemas.category import CategoryResponse
from app.core.security import get_current_user, require_roles
from app.db.models.user import User
from app.services.item.item_service import ItemService
from app.repositories.item_repository import ItemRepository

router = APIRouter(prefix="/items", tags=["items"])


@router.get(
    "",
    response_model=PaginatedResponse[ItemResponse],
    status_code=status.HTTP_200_OK
)
def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    branch_id: Optional[int] = Query(None, ge=1),
    category_id: Optional[int] = Query(None, ge=1),
    unit: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    order_by: Literal["sku", "name", "created_at", "price", "stock"] = Query("created_at"),
    order_desc: bool = Query(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List company items with filtering, search, sorting, pagination and stock per branch.
    Only authenticated active users can access this endpoint.
    """
    return ItemService.list_items(
        db=db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        is_active=is_active,
        branch_id=branch_id,
        category_id=category_id,
        unit=unit,
        search=search,
        order_by=order_by,
        order_desc=order_desc
    )


@router.post(
    "",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_item(
    item_data: ItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("MANAGER", "ADMIN"))
):
    """
    Create a new item. Only MANAGER and ADMIN can create items.
    Company is extracted from the authenticated user.
    """
    new_item = ItemService.create_item(db, item_data, current_user)
    ItemRepository.commit(db)
    return ItemService.get_item_response_with_stock(db, new_item.id, current_user)


@router.get(
    "/{item_id}",
    response_model=ItemResponse,
    status_code=status.HTTP_200_OK
)
def get_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get an item by ID. All users can view items from their company.
    """
    return ItemService.get_item_response_with_stock(db, item_id, current_user)


@router.put(
    "/{item_id}",
    response_model=ItemResponse,
    status_code=status.HTTP_200_OK
)
async def update_item(
    item_id: int,
    item_data: ItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("MANAGER", "ADMIN"))
):
    """
    Update an item. Only MANAGER and ADMIN can update items.
    
    To clear an optional field (description, price, brand),
    explicitly send the field with null/empty value.
    To preserve a field unchanged, simply don't include it in the request.
    """
    updated_item = ItemService.update_item(db, item_id, item_data, current_user)
    ItemRepository.commit(db)
    return ItemService.get_item_response_with_stock(db, updated_item.id, current_user)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN"))
):
    """
    Delete an item. Only ADMIN can delete items.
    """
    ItemService.delete_item(db, item_id, current_user)
    ItemRepository.commit(db)
    return None


@router.post(
    "/{item_id}/categories",
    response_model=ItemResponse,
    status_code=status.HTTP_200_OK
)
def assign_categories(
    item_id: int,
    category_ids: list[int],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("MANAGER", "ADMIN"))
):
    """
    Assign categories to an item. Only MANAGER and ADMIN can assign categories.
    Replaces existing categories completely.
    
    Pass an empty array [] to remove all categories from the item.
    """
    item = ItemService.assign_categories(db, item_id, category_ids, current_user)
    ItemRepository.commit(db)
    return ItemService.get_item_response_with_stock(db, item.id, current_user)


@router.get(
    "/{item_id}/categories",
    response_model=list[CategoryResponse],
    status_code=status.HTTP_200_OK
)
def get_item_categories(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all categories assigned to an item. All users can view categories from items in their company.
    """
    item = ItemService.get_item(db, item_id, current_user)
    return item.categories


@router.get(
    "/{item_id}/image",
    status_code=status.HTTP_200_OK
)
def get_item_image(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get image for an item. Only users from the item's company can access.
    Requires authentication and company ownership verification.
    Returns the image file if it exists, 404 otherwise.
    """
    return ItemService.get_item_image(db, item_id, current_user)


@router.post(
    "/{item_id}/image",
    response_model=ItemResponse,
    status_code=status.HTTP_200_OK
)
async def upload_item_image(
    item_id: int,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload or replace an image for an item."""
    image_file = await image.read()
    image_filename = image.filename or "unknown"

    item = ItemService.upload_item_image(
        db=db,
        item_id=item_id,
        current_user=current_user,
        image_file=image_file,
        image_filename=image_filename,
        image_content_type=image.content_type,
    )
    ItemRepository.commit(db)
    return ItemService.get_item_response_with_stock(db, item.id, current_user)


@router.delete(
    "/{item_id}/image",
    response_model=ItemResponse,
    status_code=status.HTTP_200_OK
)
def delete_item_image(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete the image associated to an item."""
    item = ItemService.delete_item_image(db, item_id, current_user)
    ItemRepository.commit(db)
    return ItemService.get_item_response_with_stock(db, item.id, current_user)
