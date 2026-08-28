"""Routing Engine API entry point."""

from fastapi import FastAPI

from app.api.geocode import router as geocode_router
from app.api.matrix import router as matrix_router
from app.api.navigation import router as navigation_router
from app.api.sequencing import router as sequencing_router
from app.api.zoning import router as zoning_router

app = FastAPI(
    title="Routing Engine",
    description="Geocoding and route optimisation services.",
    version="0.1.0",
)
app.include_router(geocode_router)
app.include_router(matrix_router)
app.include_router(zoning_router)
app.include_router(sequencing_router)
app.include_router(navigation_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}
