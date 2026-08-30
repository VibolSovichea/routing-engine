from fastapi import APIRouter

from app.core.config import get_settings
from app.models.zoning import ZoningRequest, ZoningResponse
from app.solvers.zoning import solve_zoning

router = APIRouter(prefix="/zoning", tags=["zoning"])


@router.post("", response_model=ZoningResponse)
async def zoning(request: ZoningRequest) -> ZoningResponse:
    return solve_zoning(
        request, time_limit_seconds=get_settings().zone_time_limit_seconds
    )
