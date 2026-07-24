"""Analytics dashboard endpoint: aggregate rollup across all campaigns."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from src.api.deps import enforce_rate_limit, get_current_user
from src.api.schemas import AnalyticsDashboardResponse
from src.db.models import User
from src.db.repositories import analytics as analytics_repo
from src.db.session import get_db

router = APIRouter(
    prefix="/api/v1/analytics", tags=["analytics"], dependencies=[Depends(enforce_rate_limit)]
)


@router.get("/dashboard", response_model=AnalyticsDashboardResponse)
def dashboard(
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AnalyticsDashboardResponse:
    rollup = analytics_repo.dashboard_for_user(db, current_user.id)
    return AnalyticsDashboardResponse(**rollup)
