from fastapi import APIRouter

from app.models.navigation import NavigationRequest, NavigationResponse
from app.services.navigation import build_navigation_deep_link

router = APIRouter(prefix="/navigation", tags=["navigation"])


@router.post("", response_model=NavigationResponse)
async def navigation(request: NavigationRequest) -> NavigationResponse:
    return build_navigation_deep_link(request)
