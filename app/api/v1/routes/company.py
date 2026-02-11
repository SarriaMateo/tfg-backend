from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.registration import CompanyRegistrationRequest
from app.schemas.company import CompanyRegistrationResponse, CompanyNameResponse
from app.services.company.registration_service import CompanyRegistrationService
from app.repositories.company_repository import CompanyRepository

router = APIRouter(prefix="/companies", tags=["companies"])


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
    "/{company_id}",
    response_model=CompanyNameResponse,
    status_code=status.HTTP_200_OK
)
def get_company_name(company_id: int, db: Session = Depends(get_db)):
    company = CompanyRepository.get_by_id(db, company_id)
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="COMPANY_NOT_FOUND"
        )
    return company
