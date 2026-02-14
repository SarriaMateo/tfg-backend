from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.branch import BranchNameResponse
from app.core.security import get_current_user
from app.db.models.user import User
from app.services.branch.branch_service import BranchService

router = APIRouter(prefix="/branches", tags=["branches"])


@router.get(
    "/company/{company_id}",
    response_model=list[BranchNameResponse],
    status_code=status.HTTP_200_OK
)
def get_branches_by_company(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    branches = BranchService.get_branches_by_company(db, company_id, current_user)
    return branches


@router.get(
    "/{branch_id}",
    response_model=BranchNameResponse,
    status_code=status.HTTP_200_OK
)
def get_branch_name(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    branch = BranchService.get_branch(db, branch_id, current_user)
    return branch
