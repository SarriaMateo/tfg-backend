from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.db.models.item import Item


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
    def commit(db: Session) -> None:
        db.commit()
