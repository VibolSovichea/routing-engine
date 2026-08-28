from urllib.parse import urlencode

from app.core.errors import BadRequestError
from app.models.navigation import (
    NavigationApp,
    NavigationRequest,
    NavigationResponse,
)

GOOGLE_MAPS_DIRECTIONS_URL = "https://www.google.com/maps/dir/?"
WAZE_APP_URL = "https://waze.com/ul?"


def build_navigation_deep_link(request: NavigationRequest) -> NavigationResponse:
    if request.app == NavigationApp.GOOGLE_MAPS:
        return _google_maps_link(request)
    if request.app == NavigationApp.WAZE:
        return _waze_link(request)
    raise BadRequestError(f"unsupported navigation app: {request.app}")


def _fmt_ll(latitude: float, longitude: float) -> str:
    return f"{latitude:.6f},{longitude:.6f}"


def _google_maps_link(request: NavigationRequest) -> NavigationResponse:
    params: dict[str, str] = {}
    if request.start is not None:
        params["origin"] = _fmt_ll(request.start.latitude, request.start.longitude)
    params["destination"] = _fmt_ll(
        request.destination.latitude, request.destination.longitude
    )
    url = GOOGLE_MAPS_DIRECTIONS_URL + urlencode(params)
    note = (
        "Google Maps will use the device's current position as the origin"
        if request.start is None
        else None
    )
    return NavigationResponse(
        app=NavigationApp.GOOGLE_MAPS,
        deep_link=url,
        note=note,
    )


def _waze_link(request: NavigationRequest) -> NavigationResponse:
    params: dict[str, str] = {}
    if request.start is not None:
        params["ll"] = _fmt_ll(request.start.latitude, request.start.longitude)
        params["navigate"] = "yes"
    params["q"] = _fmt_ll(request.destination.latitude, request.destination.longitude)
    url = WAZE_APP_URL + urlencode(params)
    return NavigationResponse(
        app=NavigationApp.WAZE,
        deep_link=url,
        note=None,
    )
