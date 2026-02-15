from sqlalchemy.orm import Session
from app.db.models.company import Company


class CompanyRepository:

    @staticmethod
    def get_by_id(db: Session, company_id: int) -> Company:
        return db.query(Company).filter(Company.id == company_id).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Company:
        return db.query(Company).filter(Company.email == email).first()

    @staticmethod
    def get_by_nif(db: Session, nif: str) -> Company:
        return db.query(Company).filter(Company.nif == nif).first()

    @staticmethod
    def create(db: Session, company: Company) -> Company:
        db.add(company)
        return company

    @staticmethod
    def update(db: Session, company: Company) -> Company:
        db.flush()
        return company

    @staticmethod
    def commit(db: Session) -> None:
        db.commit()
