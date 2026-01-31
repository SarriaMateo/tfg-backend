# app/api/v1/routes/health.py
from fastapi import APIRouter

from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends
from app.db.session import get_db


router = APIRouter(tags=["health"])

@router.get("/health")
def health_check():
    return {"status": "ok"}

## Debug to check settings - NF1
@router.get("/db-check")
def db_check(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT 1")).scalar()
    return {"db": result}

## Additional debug endpoint to create a test user - NF1
from app.db.models.user import User

@router.post("/test-user")
def create_test_user(db: Session = Depends(get_db)):
    user = User(username="test", hashed_password="test")
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id}
