from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.repositories.user_repository import UserRepository


class AuthService:

    @staticmethod
    def authenticate(db: Session, username: str, password: str) -> str:
        user = UserRepository.get_by_username(db, username)
        if user is None or not verify_password(password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="INVALID_CREDENTIALS"
            )

        access_token = create_access_token(
            {
                "sub": user.username,
                "user_id": user.id,
                "role": user.role.value if hasattr(user.role, "value") else user.role,
                "company_id": user.company_id,
                "branch_id": user.branch_id,
            }
        )
        return access_token
