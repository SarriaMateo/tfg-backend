from sqlalchemy.orm import Session
from app.db.models.branch import Branch


class BranchRepository:

    @staticmethod
    def get_by_id(db: Session, branch_id: int) -> Branch:
        return db.query(Branch).filter(Branch.id == branch_id).first()

    @staticmethod
    def get_by_company_id(db: Session, company_id: int) -> list[Branch]:
        return db.query(Branch).filter(Branch.company_id == company_id).all()
