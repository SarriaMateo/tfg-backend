# tests/api/test_company_registration.py
import pytest
from app.db.models.user import Role
from httpx import AsyncClient
from httpx import ASGITransport


@pytest.mark.asyncio
async def test_register_company_success(client):
    payload = {
        "company": {
            "name": "Acme Corp",
            "email": "contact@acme.com",
            "nif": "B12345678"
        },
        "admin_user": {
            "name": "Admin User",
            "username": "admin_acme",
            "password": "password123"
        }
    }

    response = await client.post("/api/v1/companies/register", json=payload)

    assert response.status_code == 201

    data = response.json()
    assert "company" in data
    assert "user" in data

    assert data["company"]["email"] == "contact@acme.com"
    assert data["user"]["username"] == "admin_acme"
    assert data["user"]["role"] == Role.ADMIN.value
    assert data["user"]["branch_id"] is None

@pytest.mark.asyncio
async def test_register_company_duplicate_email(client):
    payload = {
        "company": {
            "name": "Acme Corp",
            "email": "duplicate@acme.com",
        },
        "admin_user": {
            "name": "Admin User",
            "username": "admin1",
            "password": "password123"
        }
    }

    await client.post("/api/v1/companies/register", json=payload)
    response = await client.post("/api/v1/companies/register", json=payload)

    assert response.status_code == 409
    assert "COMPANY_EMAIL_ALREADY_EXISTS" in response.json()["detail"]

@pytest.mark.asyncio
async def test_register_company_duplicate_username(client):
    payload1 = {
        "company": {
            "name": "Company One",
            "email": "one@company.com",
        },
        "admin_user": {
            "name": "Admin One",
            "username": "sameuser",
            "password": "password123"
        }
    }

    payload2 = {
        "company": {
            "name": "Company Two",
            "email": "two@company.com",
        },
        "admin_user": {
            "name": "Admin Two",
            "username": "sameuser",
            "password": "password123"
        }
    }

    await client.post("/api/v1/companies/register", json=payload1)
    response = await client.post("/api/v1/companies/register", json=payload2)

    assert response.status_code == 409
    assert "USERNAME_ALREADY_EXISTS" in response.json()["detail"]

@pytest.mark.asyncio
async def test_register_company_invalid_email(client):
    payload = {
        "company": {
            "name": "Invalid Email Corp",
            "email": "not-an-email",
        },
        "admin_user": {
            "name": "Admin",
            "username": "admin_invalid",
            "password": "password123"
        }
    }

    response = await client.post("/api/v1/companies/register", json=payload)

    assert response.status_code == 400
    assert "email" in response.json()["detail"].lower()
    assert "INVALID_EMAIL_FORMAT" in response.json()["detail"]

@pytest.mark.asyncio
async def test_password_is_not_returned(client):
    payload = {
        "company": {
            "name": "Secure Corp",
            "email": "secure@corp.com",
        },
        "admin_user": {
            "name": "Admin",
            "username": "secure_admin",
            "password": "supersecret"
        }
    }

    response = await client.post("/api/v1/companies/register", json=payload)

    data = response.json()
    assert "password" not in data["user"]
    assert "hashed_password" not in data["user"]
