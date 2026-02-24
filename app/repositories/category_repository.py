from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.db.models.category import Category


class CategoryRepository:

    @staticmethod
    def get_by_id(db: Session, category_id: int) -> Category:
        return db.query(Category).filter(Category.id == category_id).first()

    @staticmethod
    def get_by_company_id(db: Session, company_id: int) -> list[Category]:
        return db.query(Category).filter(Category.company_id == company_id).all()

    @staticmethod
    def get_by_id_and_company(db: Session, category_id: int, company_id: int) -> Category:
        return db.query(Category).filter(
            and_(Category.id == category_id, Category.company_id == company_id)
        ).first()

    @staticmethod
    def create(db: Session, category: Category) -> Category:
        db.add(category)
        db.flush()
        return category

    @staticmethod
    def update(db: Session, category: Category) -> Category:
        db.flush()
        return category

    @staticmethod
    def delete(db: Session, category: Category) -> None:
        db.delete(category)
        db.flush()

    @staticmethod
    def commit(db: Session) -> None:
        db.commit()
