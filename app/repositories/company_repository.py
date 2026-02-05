from sqlalchemy.orm import Session
from app.db.models.company import Company


class CompanyRepository:

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
