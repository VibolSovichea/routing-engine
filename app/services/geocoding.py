"""Geocoding service backed by the Google Places Text Search API."""

import asyncio

import httpx

from app.core.config import settings
from app.models.geocode import (
    BatchGeocodeItem,
    BatchGeocodeRequest,
    BatchGeocodeResponse,
    GeocodeRequest,
    GeocodeResponse,
    GeocodeResult,
)

GOOGLE_PLACES_TEXTSEARCH_URL = (
    "https://maps.googleapis.com/maps/api/place/textsearch/json"
)
REQUEST_TIMEOUT_SECONDS = 10.0

MAX_CONCURRENT_REQUESTS = 10

# Placeholder heuristic until the provider exposes a real quality score.
DEFAULT_CONFIDENCE = 0.9
CONFIDENCE_THRESHOLD = 0.8


async def geocode_address(request: GeocodeRequest) -> GeocodeResponse:
    """Resolve a single address into coordinates via Google Places.

    Raises:
        httpx.HTTPStatusError: On transport errors or non-OK Places status.
        ValueError: If the upstream payload is missing expected fields.
    """
    params = {
        "query": request.address,
        "key": settings.google_maps_api_key,
    }
    if request.country_bias:
        params["region"] = request.country_bias.lower()

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
        response = await client.get(
            GOOGLE_PLACES_TEXTSEARCH_URL,
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

    result = GeocodeResult(
        latitude=location["lat"],
        longitude=location["lng"],
        plus_code=plus_code,
        confidence=DEFAULT_CONFIDENCE,
        matched_label=label,
        needs_review=DEFAULT_CONFIDENCE < CONFIDENCE_THRESHOLD,
    )
    return GeocodeResponse(query=request.address, result=result)


async def geocode_addresses_batch(batch: BatchGeocodeRequest) -> BatchGeocodeResponse:
    """Resolve many addresses concurrently, capping in-flight requests.

    Individual failures are captured per item instead of failing the batch.
    """
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
