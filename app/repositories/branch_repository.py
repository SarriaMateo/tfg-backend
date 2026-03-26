from sqlalchemy.orm import Session
from sqlalchemy import or_
from typing import Optional
from app.db.models.branch import Branch
from app.db.models.transaction import Transaction


class BranchRepository:

    @staticmethod
    def get_by_id(db: Session, branch_id: int) -> Branch:
        return db.query(Branch).filter(Branch.id == branch_id).first()

    @staticmethod
    def get_by_company_id(db: Session, company_id: int, is_active: Optional[bool] = None) -> list[Branch]:
        query = db.query(Branch).filter(Branch.company_id == company_id)
        if is_active is not None:
            query = query.filter(Branch.is_active.is_(is_active))
        return query.all()

    @staticmethod
    def get_by_name_and_company(db: Session, name: str, company_id: int) -> Branch:
        return db.query(Branch).filter(
            Branch.name == name,
            Branch.company_id == company_id
        ).first()

    @staticmethod
    def create(db: Session, branch: Branch) -> Branch:
        db.add(branch)
        db.flush()
        return branch

    @staticmethod
    def update(db: Session, branch: Branch) -> Branch:
        db.flush()
        return branch

    @staticmethod
    def delete(db: Session, branch: Branch) -> None:
        db.delete(branch)
        db.flush()

    @staticmethod
    def count_transactions_by_branch_id(db: Session, branch_id: int) -> int:
        return db.query(Transaction).filter(
            or_(
                Transaction.branch_id == branch_id,
                Transaction.destination_branch_id == branch_id,
            )
        ).count()

    @staticmethod
    def commit(db: Session) -> None:
        db.commit()
