import os
from fastapi.middleware.cors import CORSMiddleware

# Desactivar la detección de bugs de bcrypt durante inicialización
os.environ["PASSLIB_BCRYPT_TRUNCATE_ERROR"] = "false"

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from app.core.config import settings
from app.core.exception_handlers import validation_exception_handler
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.company import router as company_router

app = FastAPI(title=settings.app_name)

# Registrar exception handlers
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

# Debug to check settings - NF1
@app.get("/debug/settings")
def debug_settings():
    return {
        "app_name": settings.app_name,
        "env": settings.env,
    }

