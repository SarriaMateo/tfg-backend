from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.branch import BranchNameResponse
from app.repositories.branch_repository import BranchRepository
from app.core.security import get_current_user
from app.db.models.user import User

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
    if current_user.company_id != company_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="COMPANY_ACCESS_DENIED"
        )
    branches = BranchRepository.get_by_company_id(db, company_id)
    return branches


@router.get(
    "/{branch_id}",
    response_model=BranchNameResponse,
    status_code=status.HTTP_200_OK
)
def get_branch_name(branch_id: int, db: Session = Depends(get_db)):
    branch = BranchRepository.get_by_id(db, branch_id)
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="BRANCH_NOT_FOUND"
        )
    return branch
