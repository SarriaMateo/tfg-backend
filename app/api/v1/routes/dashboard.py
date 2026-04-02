from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import Literal

from app.core.security import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.dashboard import DashboardActivityResponse, DashboardStockRiskResponse
from app.services.dashboard.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/stock-risk",
    response_model=DashboardStockRiskResponse,
    status_code=status.HTTP_200_OK,
)
def get_stock_risk_dashboard(
    branch_id: Optional[int] = Query(None, ge=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get stock-risk dashboard metrics for one active branch or all active branches."""
    return DashboardService.get_stock_risk_metrics(
        db=db,
        current_user=current_user,
        branch_id=branch_id,
    )


@router.get(
    "/activity",
    response_model=DashboardActivityResponse,
    status_code=status.HTTP_200_OK,
)
def get_activity_dashboard(
    branch_id: Optional[int] = Query(None, ge=1),
    period: Literal["day", "week", "month", "total"] = Query("day"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get activity dashboard metrics for one active branch or all active branches."""
    return DashboardService.get_activity_metrics(
        db=db,
        current_user=current_user,
        branch_id=branch_id,
        period=period,
    )
