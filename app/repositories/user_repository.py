from sqlalchemy.orm import Session
from app.db.models.user import User


class UserRepository:

    @staticmethod
    def get_by_username(db: Session, username: str) -> User:
        return db.query(User).filter(User.username == username).first()

    @staticmethod
    def create(db: Session, user: User) -> User:
        db.add(user)
        return user
