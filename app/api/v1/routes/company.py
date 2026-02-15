from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.registration import CompanyRegistrationRequest
from app.schemas.company import CompanyRegistrationResponse, CompanyResponse, CompanyUpdate
from app.services.company.registration_service import CompanyRegistrationService
from app.services.company.company_service import CompanyService
from app.core.security import get_current_user, require_roles
from app.db.models.user import User
from app.repositories.company_repository import CompanyRepository

router = APIRouter(prefix="/company", tags=["companies"])


@router.post(
    "/register",
    response_model=CompanyRegistrationResponse,
    status_code=status.HTTP_201_CREATED
)
def register_company(
    request: CompanyRegistrationRequest,
    db: Session = Depends(get_db)
):
    company, admin_user = CompanyRegistrationService.register_company(db, request)
    return {
        "company": company,
        "user": admin_user
    }


@router.get(
    "",
    response_model=CompanyResponse,
    status_code=status.HTTP_200_OK
)
def get_company(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    company = CompanyService.get_company_for_user(db, current_user)
    return company


@router.put(
    "",
    response_model=CompanyResponse,
    status_code=status.HTTP_200_OK
)
def update_company(
    company_data: CompanyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN"))
):
    updated_company = CompanyService.update_company(
        db,
        current_user.company_id,
        company_data,
        current_user
    )
    CompanyRepository.commit(db)
    return updated_company
