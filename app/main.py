"""Routing Engine API entry point."""

from fastapi import FastAPI

from app.api.geocode import router as geocode_router

app = FastAPI(
    title="Routing Engine",
    description="Geocoding and route optimisation services.",
    version="0.1.0",
)
app.include_router(geocode_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
