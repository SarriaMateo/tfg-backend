from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.db.models.user import User, Role


class UserRepository:

    @staticmethod
    def get_by_id(db: Session, user_id: int) -> User:
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_by_username(db: Session, username: str) -> User:
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def create(db: Session, user: User) -> User:
        db.add(user)
        db.flush()
        return user

    @staticmethod
    def get_by_company_id(db: Session, company_id: int) -> list[User]:
        return db.query(User).filter(User.company_id == company_id).all()

    @staticmethod
    def get_by_company_and_branch(db: Session, company_id: int, branch_id: int) -> list[User]:
        """Get users from a specific branch and company, including users without a branch assigned."""
        from sqlalchemy import or_
        return db.query(User).filter(
            and_(
                User.company_id == company_id,
                or_(User.branch_id == branch_id, User.branch_id.is_(None))
            )
        ).all()

    @staticmethod
    def get_by_company_and_role(db: Session, company_id: int, role: Role) -> list[User]:
        return db.query(User).filter(
            and_(User.company_id == company_id, User.role == role)
        ).all()

    @staticmethod
    def count_admins_by_company(db: Session, company_id: int) -> int:
        return db.query(User).filter(
            and_(User.company_id == company_id, User.role == Role.ADMIN)
        ).count()

    @staticmethod
    def count_active_admins_by_company(db: Session, company_id: int) -> int:
        return db.query(User).filter(
            and_(
                User.company_id == company_id,
                User.role == Role.ADMIN,
                User.is_active.is_(True)
            )
        ).count()

    @staticmethod
    def count_by_branch_id(db: Session, branch_id: int) -> int:
        return db.query(User).filter(User.branch_id == branch_id).count()

    @staticmethod
    def update(db: Session, user: User) -> User:
        db.flush()
        return user

    @staticmethod
    def delete(db: Session, user: User) -> None:
        db.delete(user)
        db.flush()

    @staticmethod
    def commit(db: Session) -> None:
        db.commit()
