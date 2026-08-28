from fastapi import APIRouter, HTTPException

from app.models.navigation import NavigationRequest, NavigationResponse
from app.services.navigation import build_navigation_deep_link

router = APIRouter(prefix="/navigation", tags=["navigation"])


@router.post("", response_model=NavigationResponse)
async def navigation(request: NavigationRequest) -> NavigationResponse:
    try:
        return build_navigation_deep_link(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
