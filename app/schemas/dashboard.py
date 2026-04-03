from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field


class DashboardBranchScope(BaseModel):
    branch_id: int = Field(gt=0)
    branch_name: str


class DashboardStockBuckets(BaseModel):
    zero_stock_items: int = Field(ge=0)
    low_stock_items: int = Field(ge=0)
    healthy_stock_items: int = Field(ge=0)


class DashboardStockAlertItem(BaseModel):
    item_id: int = Field(gt=0)
    item_name: str
    item_sku: str
    stock: float
    low_stock_threshold: int = Field(ge=0)
    stock_status: str = Field(description="ZERO or LOW")


class DashboardStaleTransaction(BaseModel):
    transaction_id: int = Field(gt=0)
    operation_type: str
    status: str
    last_event_at: datetime
    days_since_last_event: int = Field(ge=0)
    origin_branch_id: int = Field(gt=0)
    origin_branch_name: str
    destination_branch_id: Optional[int] = None
    destination_branch_name: Optional[str] = None


class DashboardStockRiskBranchMetrics(BaseModel):
    branch: DashboardBranchScope
    pending_operations_count: int = Field(ge=0)
    stock_buckets: DashboardStockBuckets
    stock_alert_items: List[DashboardStockAlertItem]
    stale_transactions: List[DashboardStaleTransaction]


class DashboardStockRiskResponse(BaseModel):
    data: List[DashboardStockRiskBranchMetrics]


class DashboardActivityBranchMetrics(BaseModel):
    branch: DashboardBranchScope
    operations_count: int = Field(ge=0)
    incoming_transaction_lines_count: int = Field(ge=0)
    outgoing_transaction_lines_count: int = Field(ge=0)
    incoming_transaction_lines_by_operation: dict[str, int]
    outgoing_transaction_lines_by_operation: dict[str, int]


class DashboardActivityResponse(BaseModel):
    period: Literal["day", "week", "month", "total"] = "day"
    data: List[DashboardActivityBranchMetrics]
