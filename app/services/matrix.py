import logging

import httpx

from app.core.config import get_settings
from app.core.errors import (
    UpstreamAuthenticationError,
    UpstreamError,
    UpstreamRateLimitError,
    UpstreamUnreachableError,
)
from app.models.matrix import DistanceMatrixResponse, MatrixLocation, MatrixRequest

logger = logging.getLogger("routing_engine.services.matrix")


async def get_distance_matrix(request: MatrixRequest) -> DistanceMatrixResponse:
    all_locations: list[MatrixLocation] = [request.starting_point, *request.stops]
    coordinates = [[loc.longitude, loc.latitude] for loc in all_locations]

    body = {
        "locations": coordinates,
        "metrics": ["distance", "duration"],
    }
    settings = get_settings()
    headers = {
        "Authorization": settings.ors_api_key or "",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.ors_base_url}/v2/matrix/driving-car",
                json=body,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        logger.error("ORS matrix failed status=%s", status)
        if status == 401:
            raise UpstreamAuthenticationError("ORS authentication failed") from exc
        if status == 429:
            raise UpstreamRateLimitError("ORS rate limit exceeded") from exc
        raise UpstreamError(f"ORS matrix request failed ({status})") from exc
    except httpx.RequestError as exc:
        logger.error("ORS matrix unreachable")
        raise UpstreamUnreachableError("Could not reach ORS") from exc

    logger.info(
        "ORS matrix ok locations=%s",
        len(all_locations),
        extra={"location_count": len(all_locations)},
    )

    return DistanceMatrixResponse(
        locations=all_locations,
        distances_meters=data["distances"],
        durations_seconds=data["durations"],
    )
