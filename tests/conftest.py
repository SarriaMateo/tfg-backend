# tests/conftest.py
import os

# Disable bcrypt bug detection during initialization
os.environ["PASSLIB_BCRYPT_TRUNCATE_ERROR"] = "false"

import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.base import Base
from app.db.session import get_db

# Import all models to register them with Base.metadata
from app.db.models.company import Company
from app.db.models.user import User
from app.db.models.branch import Branch
from app.db.models.item import Item
from app.db.models.category import Category
from app.db.models.stock_movement import StockMovement
from app.db.models.association import item_categories
from app.db.models.transaction import Transaction
from app.db.models.transaction_line import TransactionLine
from app.db.models.transaction_event import TransactionEvent

SQLALCHEMY_TEST_DATABASE_URL = "sqlite+pysqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

TestingSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


@pytest.fixture(scope="session")
def db_engine():
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db_session(db_engine):
    connection = db_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
async def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)

    async with AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
