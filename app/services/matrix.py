import httpx

from app.core.config import settings
from app.models.matrix import DistanceMatrixResponse, MatrixLocation, MatrixRequest


async def get_distance_matrix(request: MatrixRequest) -> DistanceMatrixResponse:
    all_locations: list[MatrixLocation] = [request.starting_point, *request.stops]
    coordinates = [[loc.longitude, loc.latitude] for loc in all_locations]

    body = {
        "locations": coordinates,
        "metrics": ["distance", "duration"],
    }
    headers = {
        "Authorization": settings.ors_api_key,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{settings.ors_base_url}/v2/matrix/driving-car",
            json=body,
            headers=headers,
        )
        response.raise_for_status()
        data = response.json()

    return DistanceMatrixResponse(
        locations=all_locations,
        distances_meters=data["distances"],
        durations_seconds=data["durations"],
    )
