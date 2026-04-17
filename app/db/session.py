from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Debug to check settings - NF1
from sqlalchemy.orm import Session
from fastapi import Depends

DATABASE_URL = settings.database_url

engine = create_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Debug to check settings - NF1
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

