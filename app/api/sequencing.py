from fastapi import APIRouter

from app.core.config import get_settings
from app.models.sequencing import SequencingRequest, SequencingResponse
from app.solvers.sequencing import solve_sequencing

router = APIRouter(prefix="/sequencing", tags=["sequencing"])


@router.post("", response_model=SequencingResponse)
async def sequencing(request: SequencingRequest) -> SequencingResponse:
    return solve_sequencing(
        request, time_limit_seconds=get_settings().sequence_time_limit_seconds
    )
