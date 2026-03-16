import pytest
from app.core.security import hash_password, create_access_token
from app.db.models.user import User, Role
from app.db.models.company import Company
from app.db.models.branch import Branch
from app.db.models.item import Item, Unit
from app.db.models.category import Category
from app.db.models.stock_movement import StockMovement, MovementType
from app.db.models.transaction import Transaction, OperationType, TransactionStatus


@pytest.fixture
def company_with_data(db_session):
    company = Company(
        name="Items Company",
        email="items@company.com",
        nif="12345678Z"
    )
    db_session.add(company)
    db_session.flush()

    branch_a = Branch(name="Main Branch", address="Main street 1", company_id=company.id)
    branch_b = Branch(name="Secondary Branch", address="Second street 2", company_id=company.id)
    db_session.add_all([branch_a, branch_b])
    db_session.flush()

    category_food = Category(name="Food", color="#FF0000", company_id=company.id)
    category_cleaning = Category(name="Cleaning", color="#00FF00", company_id=company.id)
    db_session.add_all([category_food, category_cleaning])
    db_session.flush()

    item_1 = Item(
        name="Apple",
        sku="SKU001",
        unit=Unit.UNIT,
        brand="Fresh",
        is_active=True,
        company_id=company.id
    )
    item_2 = Item(
        name="Soap",
        sku="SKU002",
        unit=Unit.UNIT,
        brand="CleanX",
        is_active=False,
        company_id=company.id
    )
    item_3 = Item(
        name="Rice Bag",
        sku="SKU003",
        unit=Unit.KILOGRAM,
        brand="Fresh",
        is_active=True,
        company_id=company.id
    )
    item_4 = Item(
        name="Floor Tile",
        sku="SKU004",
        unit=Unit.SQ_METER,
        brand="BuildCo",
        is_active=True,
        company_id=company.id
    )
    db_session.add_all([item_1, item_2, item_3, item_4])
    db_session.flush()

    stock_transaction = Transaction(
        operation_type=OperationType.IN,
        status=TransactionStatus.COMPLETED,
        description="Seed stock for item list tests",
        branch_id=branch_a.id,
    )
    db_session.add(stock_transaction)
    db_session.flush()

    item_1.categories.append(category_food)
    item_2.categories.append(category_cleaning)
    item_3.categories.append(category_food)
    item_4.categories.append(category_cleaning)

    db_session.add_all([
        StockMovement(
            quantity=10,
            movement_type=MovementType.IN,
            item_id=item_1.id,
            branch_id=branch_a.id,
            transaction_id=stock_transaction.id
        ),
        StockMovement(
            quantity=-3,
            movement_type=MovementType.OUT,
            item_id=item_1.id,
            branch_id=branch_a.id,
            transaction_id=stock_transaction.id
        ),
        StockMovement(
            quantity=5,
            movement_type=MovementType.IN,
            item_id=item_3.id,
            branch_id=branch_b.id,
            transaction_id=stock_transaction.id
        ),
    ])

    db_session.commit()
    return {
        "company": company,
        "branches": [branch_a, branch_b],
        "categories": [category_food, category_cleaning],
        "items": [item_1, item_2, item_3, item_4],
    }


@pytest.fixture
def active_user_same_company(db_session, company_with_data):
    company = company_with_data["company"]
    user = User(
        name="Active Employee",
        username="active_items_user",
        hashed_password=hash_password("password123"),
        role=Role.EMPLOYEE,
        is_active=True,
        company_id=company.id,
        branch_id=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def active_admin_same_company(db_session, company_with_data):
    company = company_with_data["company"]
    user = User(
        name="Active Admin",
        username="active_items_admin",
        hashed_password=hash_password("password123"),
        role=Role.ADMIN,
        is_active=True,
        company_id=company.id,
        branch_id=None,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def inactive_user_same_company(db_session, company_with_data):
    company = company_with_data["company"]
    user = User(
        name="Inactive Employee",
        username="inactive_items_user",
        hashed_password=hash_password("password123"),
        role=Role.EMPLOYEE,
        is_active=False,
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
async def test_list_items_requires_active_user(client, inactive_user_same_company):
    token = build_token(inactive_user_same_company)

    response = await client.get(
        "/api/v1/items",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "USER_INACTIVE"


@pytest.mark.asyncio
async def test_list_items_returns_paginated_data_and_zero_stock(client, active_user_same_company):
    token = build_token(active_user_same_company)

    response = await client.get(
        "/api/v1/items?page=1&page_size=2",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["page"] == 1
    assert payload["page_size"] == 2
    assert payload["total"] == 3
    assert payload["total_pages"] == 2
    assert len(payload["data"]) == 2

    found_zero_stock_item = False
    for item in payload["data"]:
        for branch_stock in item["stock_by_branch"]:
            if branch_stock["stock"] == "0.000":
                found_zero_stock_item = True
                break

    assert found_zero_stock_item is True


@pytest.mark.asyncio
async def test_list_items_filters_by_is_active_unit_and_category(client, active_user_same_company, company_with_data):
    token = build_token(active_user_same_company)
    category_food = company_with_data["categories"][0]

    response = await client.get(
        f"/api/v1/items?is_active=true&unit=kg&category_id={category_food.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 1
    assert len(payload["data"]) == 1
    assert payload["data"][0]["name"] == "Rice Bag"
    assert payload["data"][0]["unit"] == "kg"


@pytest.mark.asyncio
async def test_list_items_filters_by_square_meter_unit(client, active_user_same_company):
    token = build_token(active_user_same_company)

    response = await client.get(
        "/api/v1/items?unit=m2",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 1
    assert len(payload["data"]) == 1
    assert payload["data"][0]["name"] == "Floor Tile"
    assert payload["data"][0]["unit"] == "m2"


@pytest.mark.asyncio
async def test_list_items_search_by_name_sku_and_brand(client, active_user_same_company):
    token = build_token(active_user_same_company)

    response_by_name = await client.get(
        "/api/v1/items?search=apple",
        headers={"Authorization": f"Bearer {token}"}
    )
    response_by_sku = await client.get(
        "/api/v1/items?search=SKU003",
        headers={"Authorization": f"Bearer {token}"}
    )
    response_by_brand = await client.get(
        "/api/v1/items?search=CleanX",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response_by_name.status_code == 200
    assert response_by_sku.status_code == 200
    assert response_by_brand.status_code == 200

    payload_name = response_by_name.json()
    payload_sku = response_by_sku.json()
    payload_brand = response_by_brand.json()

    assert payload_name["total"] == 1
    assert payload_name["data"][0]["name"] == "Apple"
    assert payload_sku["total"] == 1
    assert payload_sku["data"][0]["sku"] == "SKU003"
    assert payload_brand["total"] == 0
    assert payload_brand["data"] == []


@pytest.mark.asyncio
async def test_list_items_order_by_stock_desc(client, active_user_same_company):
    token = build_token(active_user_same_company)

    response = await client.get(
        "/api/v1/items?order_by=stock&order_desc=true",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 3
    assert len(payload["data"]) == 3

    first = payload["data"][0]
    second = payload["data"][1]

    first_total_stock = sum(float(branch["stock"]) for branch in first["stock_by_branch"])
    second_total_stock = sum(float(branch["stock"]) for branch in second["stock_by_branch"])

    assert first_total_stock >= second_total_stock


@pytest.mark.asyncio
async def test_list_items_admin_sees_active_and_inactive_by_default(client, active_admin_same_company):
    token = build_token(active_admin_same_company)

    response = await client.get(
        "/api/v1/items",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["total"] == 4
    item_names = [item["name"] for item in payload["data"]]
    assert "Soap" in item_names
