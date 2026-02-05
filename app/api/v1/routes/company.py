from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.registration import CompanyRegistrationRequest
from app.schemas.company import CompanyRegistrationResponse
from app.schemas.user import UserResponse
from app.services.company.registration_service import CompanyRegistrationService

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
