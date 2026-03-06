from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Union

from app.core.security import hash_password
from app.repositories.user_repository import UserRepository
from app.repositories.branch_repository import BranchRepository
from app.db.models.user import User, Role
from app.schemas.user import UserCreate, UserUpdate, UserUpdateAdmin


class UserService:
    """Business logic service for users"""

    @staticmethod
    def validate_user_active(user: User) -> None:
        """
        Validate that a user is active.
        Raises 403 Forbidden if user is not active.
        Can be used in dependencies to check is_active from JWT token's user_id.
        """
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="USER_INACTIVE"
            )

    @staticmethod
    def create_user(
        db: Session,
        user_data: UserCreate,
        admin_user: User
    ) -> User:
        """
        Create a new user. Only admins can create users.
        Validations:
        - Username must be unique across the entire application
        - If a branch is assigned, it must belong to the admin's company
        """
        # Verify that the authenticated user is active
        UserService.validate_user_active(admin_user)
        
        # Verify that the authenticated user is admin
        if admin_user.role != Role.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="INSUFFICIENT_ROLE"
            )

        # Verify that the username is unique
        existing_user = UserRepository.get_by_username(db, user_data.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="USERNAME_ALREADY_EXISTS"
            )

        # Validate that admin users cannot have a branch assigned
        if user_data.role.value == "ADMIN" and user_data.branch_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ADMIN_CANNOT_HAVE_BRANCH"
            )

        # Validate that if a branch is assigned, it belongs to the admin's company
        if user_data.branch_id:
            branch = BranchRepository.get_by_id(db, user_data.branch_id)
            if not branch:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="BRANCH_NOT_FOUND"
                )
            if branch.company_id != admin_user.company_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="BRANCH_BELONGS_TO_DIFFERENT_COMPANY"
                )

        # Create the new user
        new_user = User(
            name=user_data.name,
            username=user_data.username,
            hashed_password=hash_password(user_data.password),
            role=Role(user_data.role.value),
            is_active=True,
            company_id=admin_user.company_id,
            branch_id=user_data.branch_id
        )

        return UserRepository.create(db, new_user)

    @staticmethod
    def get_user(
        db: Session,
        user_id: int,
        current_user: User
    ) -> User:
        """
        Get a user.
        Rules:
        - Admins can view any user from their company
        - Non-admin users can only view their own profile
        """
        # Verify that the current user is active
        UserService.validate_user_active(current_user)
        
        user = UserRepository.get_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="USER_NOT_FOUND"
            )

        # If not admin, can only view their own user
        if current_user.role != Role.ADMIN:
            if current_user.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="CANNOT_VIEW_OTHER_USERS"
                )
        else:
            # If admin, can only view users from their company
            if current_user.company_id != user.company_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="USER_FROM_DIFFERENT_COMPANY"
                )

        return user

    @staticmethod
    def get_users_by_company(
        db: Session,
        current_user: User,
        branch_id: int = None,
        is_active: bool = None
    ) -> list[User]:
        """
        Get users from the current user's company with optional branch filtering and active status filtering.
        
        Rules:
        - If branch_id is None/null: Only users without branch_id (admins) can view all users from company
        - If branch_id is provided: 
          - User must have the same branch_id they are requesting
          - Returns users with that branch_id + users without branch_id
        - MANAGER/EMPLOYEE users: Always see only active users (is_active=True)
        - ADMIN users: See all users by default, unless is_active is explicitly set
        
        Args:
            db: Database session
            current_user: The authenticated user making the request
            branch_id: Optional branch_id to filter users
            is_active: Optional filter for user active status (only respected for ADMIN)
        
        Returns:
            List of User objects matching the criteria
        """
        # Verify that the authenticated user is active
        UserService.validate_user_active(current_user)
        
        # Determine if_active filter based on role
        active_filter = None
        if current_user.role != Role.ADMIN:
            # Non-admin users only see active users
            active_filter = True
        else:
            # Admin can specify is_active, or see all if not specified
            active_filter = is_active
        
        # If no branch_id filter is requested
        if branch_id is None:
            # Only users without a branch assigned can list all company users
            if current_user.branch_id is not None:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="BRANCH_USERS_CANNOT_LIST_ALL_USERS"
                )
            # Can only view all users, no specific role requirement for listing all
            return UserRepository.get_by_company_id(db, current_user.company_id, is_active=active_filter)
        
        # If a specific branch_id is requested
        else:
            # User must have the same branch_id they are requesting
            if current_user.branch_id != branch_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="BRANCH_MISMATCH"
                )
            # Return users with that branch_id + users without branch_id
            return UserRepository.get_by_company_and_branch(db, current_user.company_id, branch_id, is_active=active_filter)

    @staticmethod
    def update_user(
        db: Session,
        user_id: int,
        user_data: Union[UserUpdate, UserUpdateAdmin],
        current_user: User
    ) -> User:
        """
        Update a user.
        Rules:
        - Admins can update any user from their company
        - Non-admin users can only update their own profile and only certain fields
        """
        # Verify that the current user is active
        UserService.validate_user_active(current_user)
        
        user = UserRepository.get_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="USER_NOT_FOUND"
            )

        # Verify authorization
        is_admin = current_user.role == Role.ADMIN
        is_own_user = current_user.id == user_id

        if not is_admin and not is_own_user:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CANNOT_UPDATE_OTHER_USERS"
            )

        # If not admin but is their own user
        if not is_admin:
            # Non-admins can only update: name, username, password
            if isinstance(user_data, UserUpdateAdmin):
                if user_data.role is not None or user_data.branch_id is not None:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="CANNOT_UPDATE_ROLE_OR_BRANCH"
                    )

        # If admin, verify updating users from their company
        if is_admin:
            if current_user.company_id != user.company_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="USER_FROM_DIFFERENT_COMPANY"
                )

            # Validate role and branch changes only for admins
            if isinstance(user_data, UserUpdateAdmin):
                # Check which fields were explicitly sent
                sent_fields = user_data.model_dump(exclude_unset=True)
                
                # If changing role
                if user_data.role and user_data.role.value != user.role.value:
                    # If changing from ADMIN to another
                    if user.role == Role.ADMIN and user.is_active:
                        # Verify it's not the only active admin of the company
                        active_admin_count = UserRepository.count_active_admins_by_company(
                            db, user.company_id
                        )
                        if active_admin_count == 1:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="CANNOT_CHANGE_ROLE_LAST_ADMIN"
                            )
                    
                    # If changing to ADMIN and user has a branch
                    if user_data.role.value == "ADMIN" and user.branch_id:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="ADMIN_CANNOT_HAVE_BRANCH"
                        )

                # Validate branch only if the field was sent
                if "branch_id" in sent_fields:
                    if user_data.branch_id is not None:  # Sent with a value (not null)
                        # Check if user will be admin (either already is or being changed to admin)
                        final_role = user_data.role.value if user_data.role else user.role.value
                        if final_role == "ADMIN":
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="ADMIN_CANNOT_HAVE_BRANCH"
                            )
                        
                        branch = BranchRepository.get_by_id(db, user_data.branch_id)
                        if not branch:
                            raise HTTPException(
                                status_code=status.HTTP_404_NOT_FOUND,
                                detail="BRANCH_NOT_FOUND"
                            )
                        if branch.company_id != current_user.company_id:
                            raise HTTPException(
                                status_code=status.HTTP_400_BAD_REQUEST,
                                detail="BRANCH_BELONGS_TO_DIFFERENT_COMPANY"
                            )

        # Validate unique username if changed
        if user_data.username and user_data.username != user.username:
            existing_user = UserRepository.get_by_username(db, user_data.username)
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="USERNAME_ALREADY_EXISTS"
                )

        # Update fields
        if user_data.name:
            user.name = user_data.name
        if user_data.username:
            user.username = user_data.username
        if user_data.password:
            user.hashed_password = hash_password(user_data.password)

        # Admin-only fields
        if isinstance(user_data, UserUpdateAdmin):
            sent_fields = user_data.model_dump(exclude_unset=True)
            
            if user_data.role:
                user.role = Role(user_data.role.value)
            
            # Only update branch_id if it was explicitly sent
            if "branch_id" in sent_fields:
                user.branch_id = user_data.branch_id
            
            # Only update is_active if it was explicitly sent
            if "is_active" in sent_fields:
                # Verify cannot deactivate the only active admin of the company
                if user_data.is_active == False and user.is_active == True and user.role == Role.ADMIN:
                    active_admin_count = UserRepository.count_active_admins_by_company(
                        db, user.company_id
                    )
                    if active_admin_count == 1:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="CANNOT_DEACTIVATE_LAST_ACTIVE_ADMIN"
                        )
                
                user.is_active = user_data.is_active

        return UserRepository.update(db, user)

    @staticmethod
    def delete_user(
        db: Session,
        user_id: int,
        admin_user: User
    ) -> None:
        """
        Delete a user.
        Rules:
        - Only admins can delete users
        - Admin can only delete users from their own company
        - Cannot delete the only admin of a company
        """
        # Verify that the authenticated user is active
        UserService.validate_user_active(admin_user)
        
        # Verify is admin
        if admin_user.role != Role.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="INSUFFICIENT_ROLE"
            )

        user = UserRepository.get_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="USER_NOT_FOUND"
            )

        # Verify admin is deleting users from their company
        if admin_user.company_id != user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="USER_FROM_DIFFERENT_COMPANY"
            )

        # Verify it's not the only active admin of the company
        if user.role == Role.ADMIN and user.is_active:
            active_admin_count = UserRepository.count_active_admins_by_company(db, user.company_id)
            if active_admin_count == 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="CANNOT_DELETE_LAST_ADMIN"
                )

        UserRepository.delete(db, user)
