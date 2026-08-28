# syntax=docker/dockerfile:1
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim AS build

WORKDIR /app

# Install dependencies with a frozen lockfile (cached layer).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy the application source.
COPY app ./app

# Final runtime stage.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

# Non-root user for the runtime.
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Copy the venv and source from build stage.
COPY --from=build /app/.venv ./.venv
COPY --from=build /app/app ./app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
