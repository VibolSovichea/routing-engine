from fastapi import APIRouter

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
    return await geocode_address(request)


@router.post("/batch", response_model=BatchGeocodeResponse)
async def geocode_batch(batch: BatchGeocodeRequest) -> BatchGeocodeResponse:
    return await geocode_addresses_batch(batch)
