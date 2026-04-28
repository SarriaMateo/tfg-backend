from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from typing import Optional, Tuple
from app.db.models.item import Item, Unit
from app.db.models.association import item_categories
from app.db.models.transaction_line import TransactionLine


class ItemRepository:

    @staticmethod
    def get_by_id(db: Session, item_id: int) -> Item:
        return db.query(Item).filter(Item.id == item_id).first()

    @staticmethod
    def get_by_sku_and_company(db: Session, sku: str, company_id: int) -> Item:
        return db.query(Item).filter(
            and_(Item.sku == sku, Item.company_id == company_id)
        ).first()

    @staticmethod
    def get_by_company_id(db: Session, company_id: int) -> list[Item]:
        return db.query(Item).filter(Item.company_id == company_id).all()

    @staticmethod
    def list_items_with_filters(
        db: Session,
        company_id: int,
        page: int = 1,
        page_size: int = 20,
        is_active: Optional[bool] = None,
        category_id: Optional[int] = None,
        unit: Optional[Unit] = None,
        search: Optional[str] = None,
        order_by: str = "name",
        order_desc: bool = False
    ) -> Tuple[list[Item], int]:
        """
        List items with filters, search, pagination and sorting.
        Returns tuple of (items, total_count)
        
        Filters:
        - is_active: Filter by active status
        - category_id: Filter by category
        - unit: Filter by unit of measure
        
        Search:
        - search: Search in name, sku, and brand (case-insensitive, partial match)
        
        Ordering:
        - order_by: Field to order by (sku, name, created_at, price)
        - order_desc: True for descending, False for ascending
        """
        query = db.query(Item).filter(Item.company_id == company_id)

        # Apply filters
        if is_active is not None:
            query = query.filter(Item.is_active == is_active)
        
        if unit:
            query = query.filter(Item.unit == unit)
        
        if category_id is not None:
            # Join with item_categories association table to filter by category
            query = query.join(
                item_categories,
                Item.id == item_categories.c.item_id
            ).filter(
                item_categories.c.category_id == category_id
            )

        # Apply search
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Item.name.ilike(search_pattern),
                    Item.sku.ilike(search_pattern),
                    Item.brand.ilike(search_pattern)
                )
            )

        # Get total count before pagination
        total_count = query.count()

        # Apply ordering (excluding stock for now, handled in service)
        order_column = {
            "sku": Item.sku,
            "name": Item.name,
            "created_at": Item.created_at,
            "price": Item.price
        }.get(order_by, Item.created_at)

        if order_desc:
            query = query.order_by(order_column.desc())
        else:
            query = query.order_by(order_column.asc())

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Execute query with eager loading of categories
        items = query.options(joinedload(Item.categories)).all()

        return items, total_count

    @staticmethod
    def create(db: Session, item: Item) -> Item:
        db.add(item)
        db.flush()
        return item

    @staticmethod
    def update(db: Session, item: Item) -> Item:
        db.flush()
        return item

    @staticmethod
    def delete(db: Session, item: Item) -> None:
        db.delete(item)
        db.flush()

    @staticmethod
    def count_transaction_lines_by_item_id(db: Session, item_id: int) -> int:
        return db.query(TransactionLine).filter(TransactionLine.item_id == item_id).count()

    @staticmethod
    def commit(db: Session) -> None:
        db.commit()
