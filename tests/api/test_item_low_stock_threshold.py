import pytest

from app.core.security import create_access_token, hash_password
from app.db.models.company import Company
from app.db.models.item import Item, Unit
from app.db.models.user import User, Role


@pytest.fixture
def manager_user(db_session):
    company = Company(
        name="Threshold Company",
        email="threshold@company.com",
        nif="11223344A"
    )
    db_session.add(company)
    db_session.flush()

    user = User(
        name="Threshold Manager",
        username="threshold_manager",
        hashed_password=hash_password("password123"),
        role=Role.MANAGER,
        is_active=True,
        company_id=company.id,
        branch_id=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def build_token(user: User) -> str:
    return create_access_token({
        "sub": user.username,
        "user_id": user.id,
        "role": user.role.value,
        "company_id": user.company_id,
        "branch_id": user.branch_id,
    })


@pytest.mark.asyncio
async def test_create_item_accepts_low_stock_threshold_and_returns_it(client, manager_user):
    token = build_token(manager_user)

    response = await client.post(
        "/api/v1/items",
        json={
            "name": "Cement Bag",
            "sku": "CEMENT01",
            "unit": "kg",
            "low_stock_threshold": 7,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["low_stock_threshold"] == 7


@pytest.mark.asyncio
async def test_update_item_accepts_low_stock_threshold_and_returns_it(client, manager_user, db_session):
    item = Item(
        name="Cable Roll",
        sku="CABLE01",
        unit=Unit.METER,
        low_stock_threshold=0,
        company_id=manager_user.company_id,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    token = build_token(manager_user)

    response = await client.put(
        f"/api/v1/items/{item.id}",
        json={"low_stock_threshold": 12},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["low_stock_threshold"] == 12


@pytest.mark.asyncio
async def test_create_item_rejects_negative_low_stock_threshold(client, manager_user):
    token = build_token(manager_user)

    response = await client.post(
        "/api/v1/items",
        json={
            "name": "Paint",
            "sku": "PAINT01",
            "unit": "l",
            "low_stock_threshold": -1,
        },
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
    details = response.json()["detail"]
    assert any(err["loc"][-1] == "low_stock_threshold" for err in details)


@pytest.mark.asyncio
async def test_update_item_rejects_negative_low_stock_threshold(client, manager_user, db_session):
    item = Item(
        name="Nails Box",
        sku="NAILS01",
        unit=Unit.BOX,
        low_stock_threshold=2,
        company_id=manager_user.company_id,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    token = build_token(manager_user)

    response = await client.put(
        f"/api/v1/items/{item.id}",
        json={"low_stock_threshold": -5},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 422
    details = response.json()["detail"]
    assert any(err["loc"][-1] == "low_stock_threshold" for err in details)
