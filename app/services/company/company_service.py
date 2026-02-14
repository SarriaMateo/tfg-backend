from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.company import Company
from app.repositories.company_repository import CompanyRepository


class CompanyService:
    """Business logic service for companies"""

    @staticmethod
    def get_company_name(db: Session, company_id: int) -> Company:
        company = CompanyRepository.get_by_id(db, company_id)
        if company is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="COMPANY_NOT_FOUND"
            )
        return company
