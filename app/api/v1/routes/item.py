from fastapi import APIRouter, Depends, UploadFile, File, status, Form, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.schemas.item import ItemCreate, ItemUpdate, ItemResponse
from app.core.security import get_current_user, require_roles
from app.db.models.user import User
from app.services.item.item_service import ItemService
from app.repositories.item_repository import ItemRepository

router = APIRouter(prefix="/items", tags=["items"])


@router.post(
    "",
    response_model=ItemResponse,
    status_code=status.HTTP_201_CREATED
)
async def create_item(
    name: str = Form(...),
    sku: str = Form(...),
    unit: str = Form(...),
    description: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    brand: Optional[str] = Form(None),
    image_url_form: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("MANAGER", "ADMIN"))
):
    """
    Create a new item. Only MANAGER and ADMIN can create items.
    Company is extracted from the authenticated user.
    """
    # Build ItemCreate from form data
    item_data = ItemCreate(
        name=name,
        sku=sku,
        unit=unit,
        description=description,
        price=price,
        brand=brand,
        image_url=image_url_form
    )

    # Read image content if provided
    image_file = None
    image_filename = None
    if image:
        image_file = await image.read()
        image_filename = image.filename

    new_item = ItemService.create_item(db, item_data, current_user, image_file, image_filename)
    ItemRepository.commit(db)
    return new_item


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
    item = ItemService.get_item(db, item_id, current_user)
    return item


@router.put(
    "/{item_id}",
    response_model=ItemResponse,
    status_code=status.HTTP_200_OK
)
async def update_item(
    item_id: int,
    name: Optional[str] = Form(None),
    sku: Optional[str] = Form(None),
    unit: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    brand: Optional[str] = Form(None),
    image_url_form: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("MANAGER", "ADMIN"))
):
    """
    Update an item. Only MANAGER and ADMIN can update items.
    """
    # Build ItemUpdate from form data
    item_data = ItemUpdate(
        name=name,
        sku=sku,
        unit=unit,
        description=description,
        price=price,
        brand=brand,
        image_url=image_url_form,
        is_active=is_active
    )

    # Read image content if provided
    image_file = None
    image_filename = None
    if image:
        image_file = await image.read()
        image_filename = image.filename

    updated_item = ItemService.update_item(
        db, item_id, item_data, current_user, image_file, image_filename
    )
    ItemRepository.commit(db)
    return updated_item


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
    """
    item = ItemService.assign_categories(db, item_id, category_ids, current_user)
    ItemRepository.commit(db)
    return item
