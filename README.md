# Routing Engine

A standalone **Python microservice** that powers route planning for a delivery-management SaaS platform. For small businesses that run their own delivery drivers, this service turns a list of addresses into an optimized, driver-ready route plan — resolving places, measuring real road distances, grouping stops into work zones, ordering each zone for a driver, and linking out to turn-by-turn navigation.

The rest of the platform (auth, order intake, driver/customer portals, tracking, notifications) is a separate NestJS service that calls this one over REST.

## What it does

```
[1] Resolve place ─▶ [2] Road distance matrix ─▶ [3] Zone stops ─▶ [4] assign zones* ─▶ [5] Sequence per zone ─▶ [6] Nav deep link
                                                                  (frontend/owner)        (per-zone TSP)          (next stop)
```

Phases 1–3 & 5–6 are implemented here. **Phase 4 (zone assignment) is intentionally not in this service** — it is a human-in-the-loop step where the owner manually assigns each zone (from Phase 3) to a driver, and is handled by the NestJS/frontend.

## Architecture principle

Third-party APIs are used **only** for what they alone can provide:

- **Geocoding / place resolution** → Google Places API (Text Search)
- **Road-network distance/time matrix** → OpenRouteService (ORS) Matrix endpoint

**Everything computational** — zoning (clustering stops into groups) and sequencing (ordering stops within a zone) — runs on **our own backend via OR-Tools** (free, self-hosted), not a paid third-party optimization endpoint. This keeps marginal cost per business/driver near-zero as the platform scales.

The service is **stateless** — it has no database. The NestJS side owns all order data and stores resolved coordinates/Plus Codes on the order, so re-optimization doesn't require re-geocoding.

## Tech stack

- **Python 3** (>=3.14), FastAPI
- `httpx` for async HTTP calls to external APIs
- `pydantic` / `pydantic-settings` for schemas and config
- `ortools` for CP-SAT (zoning) and TSP-style solving (sequencing)
- Package/dependency management via `uv`

## Project structure

```
routing-engine/
  app/
    api/         # FastAPI route definitions
    core/        # config.py (pydantic-settings)
    models/      # Pydantic request/response schemas
    services/    # business logic calling external APIs
    solvers/     # OR-Tools CP-SAT (zoning) and TSP (sequencing) code
    main.py      # FastAPI app entry point
  tests/
  .env
  pyproject.toml
```

## Getting started

```bash
# Create and activate a virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv sync

# Configure environment
cp .env.example .env   # then fill in real API keys

# Run the dev server (auto-reload)
make dev
```

The API docs are available at `http://localhost:8000/docs` (Swagger) or `/redoc`.

## Configuration (`.env`)

The service **fails fast at startup** if any required variable is missing.
`extra="forbid"` means a misspelled/unknown variable is also an error.

| Variable | Default | Description |
|---|---|---|
| `ORS_API_KEY` | — | **Required.** OpenRouteService key for the distance matrix (`Authorization` header) |
| `GOOGLE_MAPS_API_KEY` | — | **Required.** Google Maps/Places key for geocoding |
| `SERVICE_API_KEY` | — | **Required.** Shared key the NestJS backend sends via `X-API-Key` on every request |
| `ORS_BASE_URL` | `https://api.openrouteservice.org` | ORS base URL |
| `MAPBOX_ACCESS_TOKEN` | — | Optional; Mapbox is not currently used (see decisions) |
| `GEOCODE_PROVIDER` | `google` | Geocoding provider selection |
| `DEFAULT_COUNTRY_CODE` | `KH` | Default geocoding country bias |
| `ZONE_TIME_LIMIT_SECONDS` | `10.0` | CP-SAT zoning solver time limit (fallback to best incumbent) |
| `SEQUENCE_TIME_LIMIT_SECONDS` | `5.0` | TSP sequencing solver time limit |
| `LOG_LEVEL` | `INFO` | Root log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LOG_FORMAT` | `json` | `json` (structured JSON to stdout) or `text` (readable local output) |
| `CORS_ALLOW_ORIGINS` | — | Optional; comma-separated browser origins allowed to call the API directly (e.g. `*`, `http://localhost:5500`). Empty disables CORS. Only needed if the frontend/test harness calls the service from a browser.

## Authentication

All endpoints except `/health` (and the OpenAPI docs pages) require a static
API key sent in the **`X-API-Key`** header. The NestJS backend must set this on
every call using the `SERVICE_API_KEY` value. Missing and invalid keys both
return `401` to avoid leaking which case occurred.

## Logging

The service emits **structured JSON logs** (one line per event) to stdout:

- Per-request correlation via a `request_id` — accepted from the upstream
  `X-Request-ID` header if present, otherwise auto-generated and echoed back
  in the response header, so the NestJS service can correlate its calls.
- Provider calls (ORS / Google) log status, counts, and outcomes.
- Solver outcomes and the global error handler log status mapping.

Set `LOG_FORMAT=text` for readable line-based output during local development.
API keys and raw addresses are never logged.

## Running with Docker

```bash
# Build and run via docker compose (reads real values from .env)
make docker-up

# Or build directly
make docker-build
docker run --rm -p 8000:8000 --env-file .env routing-engine:latest
```

The image runs as a non-root user, exposes `8000`, and includes a `/health`
healthcheck. OR-Tools native bindings are installed in the build stage, so the
solver imports are verified in the runtime image.

## API endpoints

### `POST /geocode` — resolve a place name/address
Resolves a single place name or address (English or Khmer script) to `lat/lng` + Google Plus Code + confidence score + `needs_review` flag, via Google **Places API Text Search** (not the plain Geocoding API — Places handles landmark/place-name queries far better and natively returns a `plus_code`).

**Request**
```json
{
  "address": "AEON Mall Phnom Penh",
  "country_bias": "KH"
}
```
**Response**
```json
{
  "query": "AEON Mall Phnom Penh",
  "result": {
    "latitude": 11.5621,
    "longitude": 104.9160,
    "plus_code": "C74G+JV",
    "confidence": 0.9,
    "matched_label": "AEON Mall Phnom Penh",
    "needs_review": false
  },
  "provider": "google"
}
```

### `POST /geocode/batch` — resolve up to 100 addresses
Same, concurrent (capped at 10 in-flight). Each item returns either a result or an error string — one bad address doesn't fail the batch.

### `POST /matrix` — real road-network distance/duration matrix
**Request**: `starting_point` + up to 49 `stops` (each with `label`, `latitude`, `longitude`).
**Response**: a full `N×N` matrix of real road `distances_meters` and `durations_seconds` covering all locations × all locations (not just start-to-stop). This single matrix feeds both the zoning and sequencing solvers.

The `stops` cap (49 → 50 total = 2,500 elements) stays safely under the ORS free-tier ~3,500-element limit. Revisit only after real production batch sizes are known.

### `POST /zoning` — group stops into zones (OR-Tools CP-SAT)
**Request**: `zone_count`, the `locations`, and the `distances_meters` matrix from `/matrix`.
**Response**: N zone groups, each with the indices + locations of its stops and the intra-zone travel distance.

Uses a **capacitated p-median/districting** formulation (not straight-line k-means) that minimizes total intra-zone driving distance with the real road matrix. CP-SAT is an exact solver, so it enforces a configurable time limit (`ZONE_TIME_LIMIT_SECONDS`) and falls back to the best feasible incumbent solution instead of hanging on large batches.

### `POST /sequencing` — optimal per-zone order (OR-Tools TSP)
**Request**: driver's live GPS `start_point`, the zone's `stops`, the distance (and optional duration) matrix, and a `driver_preference`.
**Response**: optimal visit order, driving legs (start → stop₁ → stop₂ …), per-leg distances/durations, and totals.

Driver preference is a **hard fixed-first-stop constraint**: `outward_in` first visits the farthest stop and works inward; `inward_out` first visits the nearest and works outward. The remaining route is then optimized as a TSP. Because `start_point` is a live position passed per call, the endpoint is stateless and can be re-run at dispatch time to re-sequence from the driver's current position.

### `POST /navigation` — next-stop deep link
**Request**: app (`google_maps` | `waze`), optional driver `start`, the single next `destination`.
**Response**: a deep link (e.g. `https://www.google.com/maps/dir/?api=1&origin=...&destination=...&travelmode=driving&dir_action=navigate` or a Waze link).

Only **one** destination is sent at a time, sidestepping the ~10-waypoint limit on consumer map apps. No route geometry is generated or stored — this is simple link building with no external API call.

## Code conventions (keep for new code)

- One concern per file: models in `app/models/`, external API clients in `app/services/`, HTTP routes in `app/api/`, solver logic in `app/solvers/`.
- Every external-facing feature gets: a Pydantic request/response schema in `models/`, a service function doing the real work, and a thin FastAPI router in `api/` that calls the service and translates errors to HTTP.
- **Error handling**: services raise *domain exceptions* defined in `app/core/errors.py` (`UpstreamAuthenticationError`, `UpstreamRateLimitError`, `UpstreamUnreachableError`, `UpstreamError`, `BadRequestError`). A single global exception handler in `main.py` maps them to HTTP (`UpstreamAuthError→502`, `RateLimit→503`, `Unreachable→503`, `UpstreamError→502`, `BadRequest→422`). Routers do **not** hand-roll `try/except` — they call the service and let the global handler respond. A "no result found" (e.g. `ZERO_RESULTS`) is **not** an error — it's a normal 200 with a `null`/`None` result field.
- **Batch endpoints** use `asyncio.gather` + `asyncio.Semaphore` to cap concurrency, and catch per-item exceptions so one bad item doesn't fail the batch.
- **GeoJSON-style APIs** (ORS) use `[longitude, latitude]` order — a common bug source.
- **Google APIs** return `lat`/`lng` as named fields and may return HTTP 200 even on failure — check the JSON `status` field, don't rely on `raise_for_status()` alone.
- **Config** is read via `get_settings()` (cached factory in `app/core/config.py`); never import a `settings` singleton. New env vars go in `.env.example` and `Settings`.

## Known decisions & rationale

- **Mapbox** was originally planned but can't be billed from a Cambodia bank account — do not reintroduce without solving billing first.
- **ORS was tried for geocoding** and found inaccurate for Cambodia addresses (thin OSM address-tagging in the region); ORS is used *only* for the road-distance matrix, where road-network data is complete.
- **Google Plus Codes** are more reliable than free-text lat/lng for Cambodia, where informal/patchy street addressing means locals often share Plus Codes directly. The `plus_code` field is first-class in the geocode response.
- **No AI geocoding fallback** — an LLM can hallucinate coordinates with no "not found" signal, a dangerous failure mode when telling drivers where to physically go. If one is ever added, it may only re-rank/disambiguate among real candidates from an API — never generate a coordinate from scratch.

## Roadmap notes

- **Zone assignment (Phase 4)** is a frontend/NestJS concern — no endpoint here.
- **Request authentication**, structured JSON logging, startup config validation, and Docker are implemented. Natural next steps are a test suite, real geocode confidence scoring, and migrating to the Google Places API v1 endpoint.
