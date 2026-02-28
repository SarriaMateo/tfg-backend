from fastapi import APIRouter, Depends, UploadFile, File, status, Form, Query, Request
from starlette.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional, Literal

from app.db.session import get_db
from app.schemas.item import ItemCreate, ItemUpdate, ItemResponse, ItemWithStock
from app.schemas.common import PaginatedResponse
from app.schemas.category import CategoryResponse
from app.core.security import get_current_user, require_roles
from app.db.models.user import User
from app.services.item.item_service import ItemService
from app.repositories.item_repository import ItemRepository

router = APIRouter(prefix="/items", tags=["items"])


@router.get(
    "",
    response_model=PaginatedResponse[ItemWithStock],
    status_code=status.HTTP_200_OK
)
def list_items(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    is_active: Optional[bool] = Query(None),
    brand: Optional[str] = Query(None),
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
        brand=brand,
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
    request: Request,
    name: Optional[str] = Form(None),
    sku: Optional[str] = Form(None),
    unit: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    price: Optional[float] = Form(None),
    brand: Optional[str] = Form(None),
    is_active: Optional[bool] = Form(None),
    delete_image: Optional[bool] = Form(None),
    image: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("MANAGER", "ADMIN"))
):
    """
    Update an item. Only MANAGER and ADMIN can update items.
    
    To clear an optional field (description, price, brand, image_url), 
    explicitly send the field with null/empty value.
    To preserve a field unchanged, simply don't include it in the request.
    To delete the current image, send delete_image=true.
    """
    # Get form data to detect which fields were actually sent
    form_data = await request.form()
    sent_fields = set(form_data.keys()) - {'image', 'delete_image'}  # Exclude file uploads and image deletion flag
    
    # Build ItemUpdate only with fields that were explicitly sent
    update_data = {}
    
    if 'name' in sent_fields:
        update_data['name'] = name
    if 'sku' in sent_fields:
        update_data['sku'] = sku
    if 'unit' in sent_fields:
        update_data['unit'] = unit
    if 'description' in sent_fields:
        update_data['description'] = description
    if 'price' in sent_fields:
        update_data['price'] = price
    if 'brand' in sent_fields:
        update_data['brand'] = brand
    if 'is_active' in sent_fields:
        update_data['is_active'] = is_active
    
    item_data = ItemUpdate(**update_data)

    # Handle image upload if provided, or delete if flag is set
    image_file = None
    image_filename = None
    
    if image:
        # New image file is being uploaded
        image_file = await image.read()
        image_filename = image.filename

    updated_item = ItemService.update_item(
        db, item_id, item_data, current_user, image_file, image_filename, delete_image or False
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
    Replaces existing categories completely.
    
    Pass an empty array [] to remove all categories from the item.
    """
    item = ItemService.assign_categories(db, item_id, category_ids, current_user)
    ItemRepository.commit(db)
    return item


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
    image_path, media_type = ItemService.get_item_image(db, item_id, current_user)
    return FileResponse(path=image_path, media_type=media_type)
