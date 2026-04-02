# TFG - Inventory Backend

Language: English | [Español](README-es.md)

Backend for a Final Degree Project (TFG): a multi-company inventory management system with branch-level scope, role-based access, stock operations, and transaction history export.

The API is built with FastAPI and SQLAlchemy, using JWT authentication and role-based business rules.

## Technology stack

- Python 3.9+
- FastAPI
- SQLAlchemy 2
- Alembic
- MySQL (runtime)
- Uvicorn
- Pydantic v2 + pydantic-settings
- python-jose + passlib (JWT and password hashing)
- WeasyPrint (PDF export)
- Pillow + pillow-heif (image support and HEIC/HEIF/AVIF to WebP conversion)
- Pytest + HTTPX

## Main features

- Company registration with automatic ADMIN user creation
- JWT login and authenticated profile endpoint
- User management with ADMIN, MANAGER, and EMPLOYEE roles
- Branch management with active/inactive status
- Category management
- Item management with:
  - filters, search, sorting, and pagination
  - stock per branch
  - category assignment
  - image upload, retrieval, and deletion
- Inventory transaction management:
  - types: IN, OUT, TRANSFER, ADJUSTMENT
  - states: PENDING, TRANSIT, COMPLETED, CANCELLED
  - historical events per transaction (CREATED, EDITED, SENT, COMPLETED, CANCELLED)
  - document attachments (PDF, Office, CSV, TXT, images)
- Transaction export to CSV and PDF (with filters)

## Architecture

Layered architecture:

- app/api/v1/routes: REST endpoints
- app/services: business logic
- app/repositories: query/persistence layer
- app/db/models: SQLAlchemy data model
- app/schemas: input/output contracts
- app/core: security, configuration, file handling, and exceptions

## Domain model (summary)

- Company
  - owns Users, Branches, Items, and Categories
- User
  - role: ADMIN | MANAGER | EMPLOYEE
  - is_active
  - may be assigned to a Branch
- Branch
  - is_active
  - groups users and transactions
- Item
  - unit of measure, commercial data, and active state
  - N:N relationship with Category
  - optional image
- Transaction
  - operation type and status
  - transaction lines
  - audit events
  - optional document
- StockMovement
  - movements generated when completing transactions

## API and prefix

- Global prefix: /api/v1
- Swagger UI: http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json

### Endpoints by module

- Auth
  - POST /auth/login
  - GET /auth/me
- Company
  - POST /company/register
  - GET /company
  - PUT /company
- Users
  - POST /users
  - GET /users
  - GET /users/{user_id}
  - PUT /users/{user_id}
  - PUT /users/{user_id}/admin
  - DELETE /users/{user_id}
- Branches
  - POST /branches
  - GET /branches
  - GET /branches/{branch_id}
  - PUT /branches/{branch_id}
  - DELETE /branches/{branch_id}
- Categories
  - POST /categories
  - GET /categories
  - GET /categories/{category_id}
  - PUT /categories/{category_id}
  - DELETE /categories/{category_id}
- Items
  - GET /items
  - POST /items
  - GET /items/{item_id}
  - PUT /items/{item_id}
  - DELETE /items/{item_id}
  - POST /items/{item_id}/categories
  - GET /items/{item_id}/categories
  - GET /items/{item_id}/image
  - POST /items/{item_id}/image
  - DELETE /items/{item_id}/image
- Dashboard
  - GET /dashboard/stock-risk
  - GET /dashboard/activity
- Transactions
  - GET /transactions
  - GET /transactions/export?format=csv|pdf
  - POST /transactions
  - GET /transactions/{transaction_id}
  - PUT /transactions/{transaction_id}
  - POST /transactions/{transaction_id}/cancel
  - POST /transactions/{transaction_id}/complete
  - POST /transactions/{transaction_id}/document
  - GET /transactions/{transaction_id}/document
  - DELETE /transactions/{transaction_id}/document
- Health/debug
  - GET /health
  - GET /db-check
  - POST /test-user (debug)
  - GET /debug/settings (debug)

## Security and authorization

- Bearer JWT authentication (OAuth2PasswordBearer)
- Login is blocked for inactive users
- Role-based access control:
  - ADMIN: full company/branch/user control
  - MANAGER: operational management (items, categories, transactions)
  - EMPLOYEE: restricted operational access
- Branch visibility rules:
  - users assigned to a branch operate within that branch scope (depending on endpoint)
- Activity rules:
  - protected endpoints validate user.is_active

## Files and media

- Base folder: media
- Item images: media/items/{company_id}
  - formats: jpg, png, webp, heic, heif, avif
  - limit: 5 MB
- Transaction documents: media/transactions/{company_id}
  - formats: PDF, Word, Excel, CSV, TXT, images
  - limit: 10 MB
- HEIC/HEIF/AVIF files are converted to WebP when stored

## Exports

- CSV and PDF in GET /transactions/export
- Only ADMIN and MANAGER can export
- Uses the same filters as the transaction list endpoint
- Internal export limits to avoid excessive loads
- PDF uses WeasyPrint and keeps a fallback path for environments without native dependencies

## Prerequisites

- Python 3.9+
- Running MySQL instance

## Environment configuration

Create a .env file in the project root.

Variables consumed by the application (app/core/config.py):

- app_name
- env
- db_user
- db_password
- db_host
- db_port
- db_name
- secret_key
- access_token_expire_minutes

Variables used by Alembic (alembic/env.py):

- DB_USER
- DB_PASSWORD
- DB_HOST
- DB_PORT
- DB_NAME

Minimal .env example compatible with both:

```env
app_name=TFG Inventory Backend
env=dev

db_user=root
db_password=your_password
db_host=127.0.0.1
db_port=3306
db_name=inventory_db

DB_USER=root
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=inventory_db

secret_key=change_this_secret
access_token_expire_minutes=60
```

## Local setup

1. Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

3. Apply migrations

```bash
alembic upgrade head
```

4. Run server

```bash
uvicorn app.main:app --reload
```

5. Open documentation

- http://localhost:8000/docs

## Tests

The test suite uses in-memory SQLite for isolation and speed (tests/conftest.py), creating the schema from Base.metadata.

Run all tests:

```bash
pytest
```

Run specific modules (examples):

```bash
pytest tests/api/test_auth_login.py
pytest tests/api/test_transaction_export_contract.py
pytest tests/services/test_transaction_export_pdf_html.py
```

Highlighted functional coverage:

- login and current user endpoint
- company, user, and branch CRUD
- active/inactive status behavior (users and branches)
- protected endpoint behavior for inactive users
- advanced item listing
- transaction CRUD and flow
- CSV/PDF export contract

## Development notes

- CORS is enabled for local frontend at http://localhost:5173
- The service exposes debug endpoints that should not be enabled in production
- Business error codes are returned in detail (for example: INSUFFICIENT_ROLE, USER_INACTIVE, ITEM_NOT_FOUND)

## Author

Mateo Sarria Franco de Sarabia

Final Degree Project - Bachelor's Degree in Telecommunication Technologies and Services Engineering

