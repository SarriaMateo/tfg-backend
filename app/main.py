from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.routes.health import router as health_router

app = FastAPI(title=settings.app_name)

app.include_router(health_router, prefix="/api/v1")

# Debug to check settings - NF1
@app.get("/debug/settings")
def debug_settings():
    return {
        "app_name": settings.app_name,
        "env": settings.env,
    }

