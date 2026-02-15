from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.company import Company
from app.db.models.user import User, Role
from app.repositories.company_repository import CompanyRepository
from app.schemas.company import CompanyUpdate


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

    @staticmethod
    def get_company_for_user(db: Session, current_user: User) -> Company:
        company = CompanyRepository.get_by_id(db, current_user.company_id)
        if company is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="COMPANY_NOT_FOUND"
            )
        return company

    @staticmethod
    def update_company(
        db: Session,
        company_id: int,
        company_data: CompanyUpdate,
        admin_user: User
    ) -> Company:
        if admin_user.role != Role.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="INSUFFICIENT_ROLE"
            )

        if admin_user.company_id != company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="COMPANY_ACCESS_DENIED"
            )

        company = CompanyRepository.get_by_id(db, company_id)
        if company is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="COMPANY_NOT_FOUND"
            )

        if company_data.email is not None and company_data.email != company.email:
            existing_company = CompanyRepository.get_by_email(db, company_data.email)
            if existing_company and existing_company.id != company.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="COMPANY_EMAIL_ALREADY_EXISTS"
                )

        if company_data.nif is not None and company_data.nif != company.nif:
            existing_company = CompanyRepository.get_by_nif(db, company_data.nif)
            if existing_company and existing_company.id != company.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="COMPANY_NIF_ALREADY_EXISTS"
                )

        if company_data.name is not None:
            company.name = company_data.name
        if company_data.email is not None:
            company.email = company_data.email
        if company_data.nif is not None:
            company.nif = company_data.nif

        return CompanyRepository.update(db, company)
