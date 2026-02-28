import os
from fastapi.middleware.cors import CORSMiddleware

# Disable bcrypt bug detection during initialization
os.environ["PASSLIB_BCRYPT_TRUNCATE_ERROR"] = "false"

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from app.core.config import settings
from app.core.exception_handlers import validation_exception_handler
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.company import router as company_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.branch import router as branch_router
from app.api.v1.routes.user import router as user_router
from app.api.v1.routes.item import router as item_router
from app.api.v1.routes.category import router as category_router

# Import all models to register them with Base.metadata
from app.db.models.company import Company
from app.db.models.user import User
from app.db.models.branch import Branch
from app.db.models.item import Item
from app.db.models.category import Category
from app.db.models.stock_movement import StockMovement
from app.db.models.association import item_categories

app = FastAPI(title=settings.app_name)

# Register exception handlers
app.add_exception_handler(RequestValidationError, validation_exception_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api/v1")
app.include_router(company_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(branch_router, prefix="/api/v1")
app.include_router(user_router, prefix="/api/v1")
app.include_router(item_router, prefix="/api/v1")
app.include_router(category_router, prefix="/api/v1")

# Debug to check settings - NF1
@app.get("/debug/settings")
def debug_settings():
    return {
        "app_name": settings.app_name,
        "env": settings.env,
    }

