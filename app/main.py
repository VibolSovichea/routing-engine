import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.geocode import router as geocode_router
from app.api.matrix import router as matrix_router
from app.api.navigation import router as navigation_router
from app.api.sequencing import router as sequencing_router
from app.api.zoning import router as zoning_router
from app.core.config import get_settings, validate_startup
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import ApiKeyMiddleware, RequestIdMiddleware

logger = logging.getLogger("routing_engine")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    validate_startup(settings)
    logger.info(
        "routing engine started",
        extra={
            "geocode_provider": settings.geocode_provider or "google",
            "ors_base_url": settings.ors_base_url,
        },
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings)

    application = FastAPI(
        title="Routing Engine",
        description="Geocoding and route optimisation services.",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.add_middleware(RequestIdMiddleware)
    application.add_middleware(ApiKeyMiddleware, service_api_key=settings.service_api_key)

    register_exception_handlers(application)

    application.include_router(geocode_router)
    application.include_router(matrix_router)
    application.include_router(zoning_router)
    application.include_router(sequencing_router)
    application.include_router(navigation_router)

    @application.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
