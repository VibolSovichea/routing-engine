import asyncio
import logging

import httpx

from app.core.config import get_settings
from app.core.errors import (
    UpstreamAuthenticationError,
    UpstreamError,
    UpstreamRateLimitError,
    UpstreamUnreachableError,
)
from app.models.geocode import (
    BatchGeocodeItem,
    BatchGeocodeRequest,
    BatchGeocodeResponse,
    GeocodeRequest,
    GeocodeResponse,
    GeocodeResult,
)

logger = logging.getLogger("routing_engine.services.geocoding")

GOOGLE_PLACES_TEXTSEARCH_URL = (
    "https://maps.googleapis.com/maps/api/place/textsearch/json"
)
REQUEST_TIMEOUT_SECONDS = 10.0

MAX_CONCURRENT_REQUESTS = 10

DEFAULT_CONFIDENCE = 0.9
CONFIDENCE_THRESHOLD = 0.8


async def geocode_address(request: GeocodeRequest) -> GeocodeResponse:
    settings = get_settings()
    params = {
        "query": request.address,
        "key": settings.google_maps_api_key,
    }
    if request.country_bias:
        params["region"] = request.country_bias.lower()

    try:
        async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS) as client:
            response = await client.get(GOOGLE_PLACES_TEXTSEARCH_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        logger.error("geocode HTTP error status=%s", status)
        if status == 401:
            raise UpstreamAuthenticationError("Google authentication failed") from exc
        if status == 429:
            raise UpstreamRateLimitError("Google rate limit exceeded") from exc
        raise UpstreamError(f"Google geocode request failed ({status})") from exc
    except httpx.RequestError as exc:
        logger.error("geocode unreachable")
        raise UpstreamUnreachableError("Could not reach Google") from exc

    status = data.get("status")
    if status == "ZERO_RESULTS":
        logger.info("geocode zero_results query=%r", request.address)
        return GeocodeResponse(query=request.address, result=None)
    if status in ("OVER_QUERY_LIMIT", "OVER_DAILY_LIMIT"):
        raise UpstreamRateLimitError(f"Google geocode quota exceeded ({status})")
    if status in ("REQUEST_DENIED", "INVALID_REQUEST"):
        raise UpstreamError(f"Google geocode request rejected ({status})")
    if status != "OK":
        raise UpstreamError(f"Google geocode unexpected status ({status})")

    if not data.get("results"):
        logger.info("geocode ok but empty results query=%r", request.address)
        return GeocodeResponse(query=request.address, result=None)

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
    logger.info("geocode ok query=%r matched=%r", request.address, label)
    return GeocodeResponse(query=request.address, result=result)


async def geocode_addresses_batch(batch: BatchGeocodeRequest) -> BatchGeocodeResponse:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def _geocode_one(req: GeocodeRequest) -> BatchGeocodeItem:
        async with semaphore:
            try:
                response = await geocode_address(req)
                return BatchGeocodeItem(response=response)
            except Exception as exc:
                logger.warning(
                    "batch geocode item failed query=%r: %s", req.address, exc
                )
                return BatchGeocodeItem(error=str(exc))

    results = await asyncio.gather(*(_geocode_one(req) for req in batch.addresses))
    return BatchGeocodeResponse(results=list(results))
