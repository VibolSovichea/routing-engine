import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("routing_engine.errors")


class RoutingEngineError(Exception):
    status_code = 500
    default_detail = "internal error"


class UpstreamAuthenticationError(RoutingEngineError):
    status_code = 502
    default_detail = "upstream authentication failed"


class UpstreamRateLimitError(RoutingEngineError):
    status_code = 503
    default_detail = "upstream rate limit exceeded"


class UpstreamUnreachableError(RoutingEngineError):
    status_code = 503
    default_detail = "could not reach upstream service"


class UpstreamError(RoutingEngineError):
    status_code = 502
    default_detail = "upstream request failed"


class BadRequestError(RoutingEngineError):
    status_code = 422
    default_detail = "invalid request"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(RoutingEngineError)
    async def _handle_domain_error(
        _request: Request, exc: RoutingEngineError
    ) -> JSONResponse:
        detail = str(exc) or exc.default_detail
        if exc.status_code >= 500:
            logger.error(
                "domain error -> %s", exc.status_code,
                extra={"detail": detail},
                exc_info=True,
            )
        else:
            logger.warning("domain error -> %s: %s", exc.status_code, detail)
        return JSONResponse(status_code=exc.status_code, content={"detail": detail})
