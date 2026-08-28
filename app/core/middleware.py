import secrets
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import request_id_var

X_API_KEY_HEADER = "X-API-Key"
X_REQUEST_ID_HEADER = "X-Request-ID"

PUBLIC_PATHS = {"/health", "/docs", "/redoc", "/openapi.json"}


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(X_REQUEST_ID_HEADER) or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers[X_REQUEST_ID_HEADER] = request_id
        return response


class ApiKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, service_api_key: str) -> None:
        super().__init__(app)
        self._service_api_key = service_api_key

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path
        if path in PUBLIC_PATHS or path.startswith(("/docs", "/redoc", "/openapi")):
            return await call_next(request)

        provided = request.headers.get(X_API_KEY_HEADER)
        if not provided or not secrets.compare_digest(
            provided, self._service_api_key
        ):
            return Response(
                status_code=401,
                content='{"detail":"unauthorized"}',
                media_type="application/json",
            )
        return await call_next(request)
