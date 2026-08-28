from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.sequencing import SequencingRequest, SequencingResponse
from app.solvers.sequencing import solve_sequencing

router = APIRouter(prefix="/sequencing", tags=["sequencing"])


@router.post("", response_model=SequencingResponse)
async def sequencing(request: SequencingRequest) -> SequencingResponse:
    try:
        return solve_sequencing(
            request, time_limit_seconds=settings.sequence_time_limit_seconds
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
