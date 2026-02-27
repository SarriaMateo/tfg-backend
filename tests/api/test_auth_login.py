import pytest
from app.core.security import hash_password
from app.db.models.user import Role, User


@pytest.mark.asyncio
async def test_login_success(client, db_session):
    user = User(
        name="Login User",
        username="login_user",
        hashed_password=hash_password("password123"),
        role=Role.MANAGER,
        company_id=1,
        branch_id=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    payload = {
        "username": "login_user",
        "password": "password123",
    }

    response = await client.post("/api/v1/auth/login", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert "user" not in data


@pytest.mark.asyncio
async def test_login_invalid_password(client, db_session):
    user = User(
        name="Login User",
        username="login_user2",
        hashed_password=hash_password("password123"),
        role=Role.EMPLOYEE,
        company_id=1,
        branch_id=2,
    )
    db_session.add(user)
    db_session.commit()

    payload = {
        "username": "login_user2",
        "password": "wrongpassword",
    }

    response = await client.post("/api/v1/auth/login", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "INVALID_CREDENTIALS"


@pytest.mark.asyncio
async def test_login_user_not_found(client):
    payload = {
        "username": "missing_user",
        "password": "password123",
    }

    response = await client.post("/api/v1/auth/login", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "INVALID_CREDENTIALS"

@pytest.mark.asyncio
async def test_login_inactive_user(client, db_session):
    """Test that inactive users cannot login"""
    user = User(
        name="Inactive User",
        username="inactive_user",
        hashed_password=hash_password("password123"),
        role=Role.EMPLOYEE,
        is_active=False,
        company_id=1,
        branch_id=None,
    )
    db_session.add(user)
    db_session.commit()

    payload = {
        "username": "inactive_user",
        "password": "password123",
    }

    response = await client.post("/api/v1/auth/login", json=payload)

    assert response.status_code == 403
    assert response.json()["detail"] == "USER_INACTIVE"