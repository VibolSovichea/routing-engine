from pydantic import BaseModel, Field


class GeocodeRequest(BaseModel):
    address: str = Field(
        ..., min_length=1, description="Place name or address to resolve"
    )
    country_bias: str | None = Field(
        default=None, description="ISO country code to bias results, e.g. 'KH'"
    )


class GeocodeResult(BaseModel):
    latitude: float
    longitude: float
    plus_code: str | None
    confidence: float
    matched_label: str
    needs_review: bool


class GeocodeResponse(BaseModel):
    query: str
    result: GeocodeResult | None
    provider: str = "google"

class BatchGeocodeRequest(BaseModel):
    addresses: list[GeocodeRequest] = Field(..., min_length=1, max_length=100)


class BatchGeocodeItem(BaseModel):
    response: GeocodeResponse | None = None
    error: str | None = None


class BatchGeocodeResponse(BaseModel):
    results: list[BatchGeocodeItem]
