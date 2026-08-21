import asyncio

import httpx

from app.models.geocode import (
    BatchGeocodeItem,
    BatchGeocodeRequest,
    BatchGeocodeResponse,
)

MAX_CONCURRENT_REQUESTS = 10

from app.core.config import settings
from app.models.geocode import GeocodeRequest, GeocodeResponse, GeocodeResult

CONFIDENCE_THRESHOLD = 0.8


async def geocode_address(request: GeocodeRequest) -> GeocodeResponse:
    params = {
        "query": request.address,
        "key": settings.google_maps_api_key,
    }
    if request.country_bias:
        params["region"] = request.country_bias.lower()

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params=params,
        )
        response.raise_for_status()
        data = response.json()

    status = data.get("status")
    if status == "ZERO_RESULTS":
        return GeocodeResponse(query=request.address, result=None)
    if status != "OK":
        raise httpx.HTTPStatusError(
            f"Google Places error: {status}",
            request=response.request,
            response=response,
        )

    top = data["results"][0]
    location = top["geometry"]["location"]
    plus_code = top.get("plus_code", {}).get("compound_code")
    label = top.get("formatted_address") or top.get("name")

    confidence = 0.9

    result = GeocodeResult(
        latitude=location["lat"],
        longitude=location["lng"],
        plus_code=plus_code,
        confidence=confidence,
        matched_label=label,
        needs_review=confidence < CONFIDENCE_THRESHOLD,
    )
    return GeocodeResponse(query=request.address, result=result)


async def geocode_addresses_batch(batch: BatchGeocodeRequest) -> BatchGeocodeResponse:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def _geocode_one(req: GeocodeRequest) -> BatchGeocodeItem:
        async with semaphore:
            try:
                response = await geocode_address(req)
                return BatchGeocodeItem(response=response)
            except Exception as exc:
                return BatchGeocodeItem(error=str(exc))

    results = await asyncio.gather(*(_geocode_one(req) for req in batch.addresses))
    return BatchGeocodeResponse(results=list(results))
