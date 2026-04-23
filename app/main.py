import os
from fastapi.middleware.cors import CORSMiddleware

# Disable bcrypt bug detection during initialization
os.environ["PASSLIB_BCRYPT_TRUNCATE_ERROR"] = "false"

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.config import settings
from app.core.exception_handlers import (
    validation_exception_handler,
    rate_limit_exception_handler,
)
from app.core.rate_limit import limiter
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.company import router as company_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.branch import router as branch_router
from app.api.v1.routes.user import router as user_router
from app.api.v1.routes.item import router as item_router
from app.api.v1.routes.category import router as category_router
from app.api.v1.routes.transaction import router as transaction_router
from app.api.v1.routes.dashboard import router as dashboard_router

# Import all models to register them with Base.metadata
from app.db.models.company import Company
from app.db.models.user import User
from app.db.models.branch import Branch
from app.db.models.item import Item
from app.db.models.category import Category
from app.db.models.stock_movement import StockMovement
from app.db.models.association import item_categories
from app.db.models.transaction import Transaction
from app.db.models.transaction_event import TransactionEvent
from app.db.models.transaction_line import TransactionLine

app = FastAPI(title=settings.app_name)
app.state.limiter = limiter

# Register exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://itematic.mateosarria.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(company_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(branch_router, prefix="/api/v1")
app.include_router(user_router, prefix="/api/v1")
app.include_router(item_router, prefix="/api/v1")
app.include_router(category_router, prefix="/api/v1")
app.include_router(transaction_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
