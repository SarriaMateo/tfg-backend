import pytest
from app.core.security import create_access_token, hash_password
from app.db.models.user import Role, User


@pytest.mark.asyncio
async def test_get_me_success(client, db_session):
    user = User(
        name="Test User",
        username="testuser",
        hashed_password=hash_password("password123"),
        role=Role.MANAGER,
        company_id=1,
        branch_id=2,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token({
        "sub": user.username,
        "user_id": user.id,
        "role": user.role.value,
        "company_id": user.company_id,
        "branch_id": user.branch_id,
    })

    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == user.id
    assert data["username"] == "testuser"
    assert data["name"] == "Test User"
    assert data["role"] == Role.MANAGER.value
    assert data["company_id"] == 1
    assert data["branch_id"] == 2
    assert "hashed_password" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_get_me_without_token(client):
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client):
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid_token"}
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "INVALID_CREDENTIALS"
