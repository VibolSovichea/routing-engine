from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.zoning import ZoningRequest, ZoningResponse
from app.solvers.zoning import solve_zoning

router = APIRouter(prefix="/zoning", tags=["zoning"])


@router.post("", response_model=ZoningResponse)
async def zoning(request: ZoningRequest) -> ZoningResponse:
    try:
        return solve_zoning(
            request, time_limit_seconds=settings.zone_time_limit_seconds
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
