# app/api/v1/routes/health.py
from fastapi import APIRouter


router = APIRouter(tags=["health"])

@router.get("/health")
def health_check():
    return {"status": "ok"}
