import httpx
from fastapi import APIRouter, HTTPException

from app.models.matrix import DistanceMatrixResponse, MatrixRequest
from app.services.matrix import get_distance_matrix

router = APIRouter(prefix="/matrix", tags=["matrix"])


@router.post("", response_model=DistanceMatrixResponse)
async def distance_matrix(request: MatrixRequest) -> DistanceMatrixResponse:
    try:
        return await get_distance_matrix(request)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 401:
            raise HTTPException(
                status_code=502, detail="ORS authentication failed"
            ) from exc
        if status == 429:
            raise HTTPException(
                status_code=503, detail="ORS rate limit exceeded"
            ) from exc
        raise HTTPException(
            status_code=502, detail=f"ORS matrix request failed ({status})"
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(status_code=503, detail="Could not reach ORS") from exc
