from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from typing import Tuple

from app.db.models.company import Company
from app.db.models.user import User
from app.repositories.company_repository import CompanyRepository
from app.repositories.user_repository import UserRepository
from app.schemas.registration import CompanyRegistrationRequest
from app.schemas.user import UserRole
from app.core.security import hash_password


class CompanyRegistrationService:

    @staticmethod
    def register_company(
        db: Session,
        data: CompanyRegistrationRequest
    ) -> Tuple[Company, User]:

        # 1. Reglas de unicidad
        if CompanyRepository.get_by_email(db, data.company.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="COMPANY_EMAIL_ALREADY_EXISTS"
            )

        if data.company.nif and CompanyRepository.get_by_nif(db, data.company.nif):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="COMPANY_NIF_ALREADY_EXISTS"
            )

        if UserRepository.get_by_username(db, data.admin_user.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="USERNAME_ALREADY_EXISTS"
            )

        # 2. Crear Company
        company = Company(
            name=data.company.name,
            email=data.company.email,
            nif=data.company.nif
        )

        CompanyRepository.create(db, company)
        db.flush()  # obtenemos company.id sin commit

        # 3. Crear User ADMIN
        admin_user = User(
            name=data.admin_user.name,
            username=data.admin_user.username,
            hashed_password=hash_password(data.admin_user.password),
            role=UserRole.ADMIN,
            company_id=company.id,
            branch_id=None
        )

        UserRepository.create(db, admin_user)

        # 4. Commit transaccional
        db.commit()
        db.refresh(company)
        db.refresh(admin_user)

        return company, admin_user
