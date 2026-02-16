import pytest
from app.core.security import create_access_token, hash_password
from app.db.models.company import Company
from app.db.models.user import Role, User


@pytest.fixture
def admin_user(db_session):
    company = Company(
        name="Acme Corp",
        email="acme@corp.com",
        nif="B12345678"
    )
    db_session.add(company)
    db_session.flush()

    user = User(
        name="Admin User",
        username="admin_acme",
        hashed_password=hash_password("admin123"),
        role=Role.ADMIN,
        company_id=company.id,
        branch_id=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def employee_user(db_session, admin_user):
    user = User(
        name="Employee User",
        username="employee_acme",
        hashed_password=hash_password("emp123"),
        role=Role.EMPLOYEE,
        company_id=admin_user.company_id,
        branch_id=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def other_company_admin(db_session):
    company = Company(
        name="Other Corp",
        email="other@corp.com",
        nif="C87654321"
    )
    db_session.add(company)
    db_session.flush()

    user = User(
        name="Other Admin",
        username="admin_other",
        hashed_password=hash_password("other123"),
        role=Role.ADMIN,
        company_id=company.id,
        branch_id=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def get_token(user):
    return create_access_token({
        "sub": user.username,
        "user_id": user.id,
        "role": user.role.value,
        "company_id": user.company_id,
        "branch_id": user.branch_id,
    })


@pytest.mark.asyncio
async def test_get_company_as_admin(client, admin_user):
    token = get_token(admin_user)

    response = await client.get(
        "/api/v1/company",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == admin_user.company_id
    assert data["email"] == "acme@corp.com"


@pytest.mark.asyncio
async def test_get_company_as_employee(client, employee_user):
    token = get_token(employee_user)

    response = await client.get(
        "/api/v1/company",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == employee_user.company_id
    assert data["name"] == "Acme Corp"


@pytest.mark.asyncio
async def test_update_company_as_admin(client, admin_user):
    token = get_token(admin_user)

    payload = {
        "name": "Acme Updated",
        "email": "updated@corp.com"
    }

    response = await client.put(
        "/api/v1/company",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Acme Updated"
    assert data["email"] == "updated@corp.com"


@pytest.mark.asyncio
async def test_update_company_as_employee_forbidden(client, employee_user):
    token = get_token(employee_user)

    payload = {
        "name": "Should Not Update"
    }

    response = await client.put(
        "/api/v1/company",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "INSUFFICIENT_ROLE"


@pytest.mark.asyncio
async def test_update_company_duplicate_email(client, admin_user, other_company_admin):
    token = get_token(admin_user)

    payload = {
        "email": "other@corp.com"
    }

    response = await client.put(
        "/api/v1/company",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "COMPANY_EMAIL_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_update_company_duplicate_nif(client, admin_user, other_company_admin):
    token = get_token(admin_user)

    payload = {
        "nif": "C87654321"
    }

    response = await client.put(
        "/api/v1/company",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "COMPANY_NIF_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_update_company_isolated_by_token(client, admin_user, other_company_admin):
    token = get_token(other_company_admin)

    payload = {
        "name": "Other Updated"
    }

    response = await client.put(
        "/api/v1/company",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == other_company_admin.company_id
    assert data["name"] == "Other Updated"


@pytest.mark.asyncio
async def test_update_company_set_nif_to_null(client, admin_user, db_session):
    token = get_token(admin_user)

    payload = {
        "nif": None
    }

    response = await client.put(
        "/api/v1/company",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["nif"] is None

    # Verify in DB
    db_session.refresh(db_session.get(Company, admin_user.company_id))
    company = db_session.get(Company, admin_user.company_id)
    assert company.nif is None


@pytest.mark.asyncio
async def test_update_company_without_nif_keeps_current(client, admin_user, db_session):
    token = get_token(admin_user)

    # Update only name, not sending nif
    payload = {
        "name": "Name Only Update"
    }

    response = await client.put(
        "/api/v1/company",
        json=payload,
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Name Only Update"
    assert data["nif"] == "B12345678"  # Should keep original NIF

