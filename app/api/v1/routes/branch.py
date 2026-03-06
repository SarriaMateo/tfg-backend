from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.schemas.branch import BranchCreate, BranchUpdate, BranchResponse
from app.core.security import get_current_user, require_roles
from app.db.models.user import User
from app.services.branch.branch_service import BranchService
from app.repositories.branch_repository import BranchRepository

router = APIRouter(prefix="/branches", tags=["branches"])


@router.post(
    "",
    response_model=BranchResponse,
    status_code=status.HTTP_201_CREATED
)
def create_branch(
    branch_data: BranchCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN"))
):
    """
    Create a new branch in the authenticated user's company.
    Only admins can create branches.
    """
    new_branch = BranchService.create_branch(db, branch_data, current_user)
    BranchRepository.commit(db)
    return new_branch


@router.get(
    "",
    response_model=list[BranchResponse],
    status_code=status.HTTP_200_OK
)
def get_branches_by_company(
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get branches from the authenticated user's company with optional active status filter.
    
    Query parameters:
    - is_active: Optional active status filter (only ADMIN users can vary this; others always see active branches)
    
    - MANAGER/EMPLOYEE: Always see only active branches
    - ADMIN: See all branches by default, or filter by is_active if specified
    """
    branches = BranchService.get_branches_by_company(db, current_user, is_active)
    return branches


@router.get(
    "/{branch_id}",
    response_model=BranchResponse,
    status_code=status.HTTP_200_OK
)
def get_branch_name(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    branch = BranchService.get_branch(db, branch_id, current_user)
    return branch


@router.put(
    "/{branch_id}",
    response_model=BranchResponse,
    status_code=status.HTTP_200_OK
)
def update_branch(
    branch_id: int,
    branch_data: BranchUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN"))
):
    """
    Update a branch.
    Only admins can update branches in their company.
    """
    updated_branch = BranchService.update_branch(db, branch_id, branch_data, current_user)
    BranchRepository.commit(db)
    return updated_branch


@router.delete(
    "/{branch_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_branch(
    branch_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN"))
):
    """
    Delete a branch.
    Only admins can delete branches from their company.
    Cannot delete a branch if it has associated users.
    """
    BranchService.delete_branch(db, branch_id, current_user)
    BranchRepository.commit(db)
    return None
