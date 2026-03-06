from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.db.session import get_db
from app.db.models.user import User
from app.core.security import get_current_user, require_roles
from app.schemas.user import UserResponse, UserCreate, UserUpdate, UserUpdateAdmin
from app.services.user.user_service import UserService
from app.repositories.user_repository import UserRepository

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN"))
):
    """
    Create a new user.
    Only admins can create users in their company.
    Username must be unique.
    """
    new_user = UserService.create_user(db, user_data, current_user)
    UserRepository.commit(db)
    return new_user


@router.get(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK
)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get user information.
    Admins can view any user from their company.
    Other users can only view their own profile.
    """
    user = UserService.get_user(db, user_id, current_user)
    return user


@router.get(
    "",
    response_model=list[UserResponse],
    status_code=status.HTTP_200_OK
)
def get_company_users(
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get users from the authenticated user's company with optional active status filter.
    
    Query parameters:
    - is_active: Optional active status filter (only ADMIN users can vary this; others always see active users)
    
    - If user has no branch_id: Returns all users from company
    - If user has branch_id: Returns users with that branch_id + users without branch_id
    - MANAGER/EMPLOYEE: Always see only active users
    - ADMIN: See all users by default, or filter by is_active if specified
    """
    users = UserService.get_users_by_company(db, current_user, is_active)
    return users


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK
)
def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update a user.
    Admins can update any user from their company (all fields).
    Other users can only update their own profile (name, username, password).
    """
    updated_user = UserService.update_user(db, user_id, user_data, current_user)
    UserRepository.commit(db)
    return updated_user


@router.put(
    "/{user_id}/admin",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK
)
def update_user_admin(
    user_id: int,
    user_data: UserUpdateAdmin,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN"))
):
    """
    Update a user (admin only endpoint).
    Admins can update all fields including role and branch_id.
    """
    updated_user = UserService.update_user(db, user_id, user_data, current_user)
    UserRepository.commit(db)
    return updated_user


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN"))
):
    """
    Delete a user.
    Only admins can delete users from their company.
    Cannot delete the last admin of a company.
    """
    UserService.delete_user(db, user_id, current_user)
    UserRepository.commit(db)
    return None
