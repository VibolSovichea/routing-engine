import httpx
from fastapi import APIRouter, HTTPException

from app.core.config import settings
from app.models.geocode import (
    BatchGeocodeRequest,
    BatchGeocodeResponse,
    GeocodeRequest,
    GeocodeResponse,
)
from app.services.geocoding import geocode_address, geocode_addresses_batch

router = APIRouter(prefix="/geocode", tags=["geocode"])


@router.post("", response_model=GeocodeResponse)
async def geocode(request: GeocodeRequest) -> GeocodeResponse:
    provider = settings.geocode_provider or "google"
    try:
        return await geocode_address(request)
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        if status == 401:
            raise HTTPException(
                status_code=502, detail=f"{provider} authentication failed"
            ) from exc
        if status == 429:
            raise HTTPException(
                status_code=503, detail=f"{provider} rate limit exceeded"
            ) from exc
        raise HTTPException(
            status_code=502, detail=f"{provider} request failed ({status})"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=503, detail=f"Could not reach {provider}"
        ) from exc


@router.post("/batch", response_model=BatchGeocodeResponse)
async def geocode_batch(batch: BatchGeocodeRequest) -> BatchGeocodeResponse:
    return await geocode_addresses_batch(batch)
