from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models.user import User
from app.core.security import get_current_user, require_roles
from app.schemas.user import UserResponse, UserCreate, UserUpdate, UserUpdateAdmin
from app.services.user.user_service import UserService
from app.repositories.user_repository import UserRepository

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/company/{company_id}",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def create_user(
    company_id: int,
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN"))
):
    """
    Create a new user.
    Only admins can create users in their company.
    Username must be unique.
    """
    new_user = UserService.create_user(db, user_data, company_id, current_user)
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
    "/company/{company_id}/all",
    response_model=list[UserResponse],
    status_code=status.HTTP_200_OK
)
def get_company_users(
    company_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("ADMIN"))
):
    """
    Get all users from a company.
    Only admins from that company can view them.
    """
    users = UserService.get_users_by_company(db, company_id, current_user)
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
