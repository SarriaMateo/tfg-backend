from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models.branch import Branch
from app.db.models.user import User, Role
from app.repositories.branch_repository import BranchRepository
from app.repositories.user_repository import UserRepository
from app.schemas.branch import BranchCreate, BranchUpdate
from app.services.user.user_service import UserService


class BranchService:
    """Business logic service for branches"""

    @staticmethod
    def create_branch(
        db: Session,
        branch_data: BranchCreate,
        admin_user: User
    ) -> Branch:
        UserService.validate_user_active(admin_user)
        
        if admin_user.role != Role.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="INSUFFICIENT_ROLE"
            )

        # Verify branch name is unique within company
        existing_branch = BranchRepository.get_by_name_and_company(
            db, branch_data.name, admin_user.company_id
        )
        if existing_branch:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="BRANCH_NAME_ALREADY_EXISTS"
            )

        branch = Branch(
            name=branch_data.name,
            address=branch_data.address,
            company_id=admin_user.company_id
        )

        return BranchRepository.create(db, branch)

    @staticmethod
    def get_branch(
        db: Session,
        branch_id: int,
        current_user: User
    ) -> Branch:
        UserService.validate_user_active(current_user)
        
        branch = BranchRepository.get_by_id(db, branch_id)
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="BRANCH_NOT_FOUND"
            )

        if branch.company_id != current_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="BRANCH_FROM_DIFFERENT_COMPANY"
            )

        if current_user.role != Role.ADMIN:
            if current_user.branch_id is not None and current_user.branch_id != branch_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="BRANCH_ACCESS_DENIED"
                )

        return branch

    @staticmethod
    def get_branches_by_company(
        db: Session,
        current_user: User
    ) -> list[Branch]:
        """
        Get all branches from the authenticated user's company.
        All active users can access all branches of their company.
        """
        UserService.validate_user_active(current_user)
        
        return BranchRepository.get_by_company_id(db, current_user.company_id)

    @staticmethod
    def update_branch(
        db: Session,
        branch_id: int,
        branch_data: BranchUpdate,
        admin_user: User
    ) -> Branch:
        UserService.validate_user_active(admin_user)
        
        if admin_user.role != Role.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="INSUFFICIENT_ROLE"
            )

        branch = BranchRepository.get_by_id(db, branch_id)
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="BRANCH_NOT_FOUND"
            )

        if branch.company_id != admin_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="COMPANY_ACCESS_DENIED"
            )

        # Verify branch name is unique within company (if changing name)
        if branch_data.name is not None and branch_data.name != branch.name:
            existing_branch = BranchRepository.get_by_name_and_company(
                db, branch_data.name, admin_user.company_id
            )
            if existing_branch:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="BRANCH_NAME_ALREADY_EXISTS"
                )

        # Validate is_active: cannot deactivate if branch has users
        if branch_data.is_active is not None and branch_data.is_active == False and branch.is_active == True:
            users_count = UserRepository.count_by_branch_id(db, branch_id)
            if users_count > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="CANNOT_DEACTIVATE_BRANCH_WITH_USERS"
                )

        if branch_data.name is not None:
            branch.name = branch_data.name
        if branch_data.address is not None:
            branch.address = branch_data.address
        if branch_data.is_active is not None:
            branch.is_active = branch_data.is_active

        return BranchRepository.update(db, branch)

    @staticmethod
    def delete_branch(
        db: Session,
        branch_id: int,
        admin_user: User
    ) -> None:
        UserService.validate_user_active(admin_user)
        
        if admin_user.role != Role.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="INSUFFICIENT_ROLE"
            )

        branch = BranchRepository.get_by_id(db, branch_id)
        if not branch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="BRANCH_NOT_FOUND"
            )

        if branch.company_id != admin_user.company_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="COMPANY_ACCESS_DENIED"
            )

        users_count = UserRepository.count_by_branch_id(db, branch_id)
        if users_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="BRANCH_HAS_USERS"
            )

        BranchRepository.delete(db, branch)
