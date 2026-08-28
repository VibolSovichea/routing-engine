from fastapi import APIRouter

from app.models.matrix import DistanceMatrixResponse, MatrixRequest
from app.services.matrix import get_distance_matrix

router = APIRouter(prefix="/matrix", tags=["matrix"])


@router.post("", response_model=DistanceMatrixResponse)
async def distance_matrix(request: MatrixRequest) -> DistanceMatrixResponse:
    return await get_distance_matrix(request)
