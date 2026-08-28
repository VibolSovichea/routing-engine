# Routing Engine — Continuation Instructions for AI Coding Agent

## Context

This is a standalone Python microservice ("Routing Engine") that is part of a larger delivery-management SaaS platform for small business owners who run their own delivery drivers (an alternative to Grab/foodpanda/DoorDash for businesses that already have their own fleet). The rest of the platform (auth, order intake, driver/customer portals, tracking, notifications) is a separate NestJS service — **not your concern**. This service is called by that NestJS service via REST.

**Your job**: continue implementing this service feature-by-feature, following the architecture, conventions, and decisions already locked in below. Do not revisit or re-litigate decisions already made unless something is factually broken (e.g. an API contract that doesn't work as documented) — flag it, don't silently change it.

---

## Architecture principle (do not violate)

Third-party APIs are used **only** for what they alone can provide:

- **Geocoding / place resolution** → Google Places API (Text Search)
- **Road-network distance/time matrix** → OpenRouteService (ORS) Matrix endpoint

**Everything computational** — zoning (clustering stops into groups) and sequencing (ordering stops within a zone) — runs on **our own backend via OR-Tools** (free, self-hosted), not a paid third-party optimization endpoint. This keeps marginal cost per business/driver near-zero as the platform scales, instead of paying a per-optimization-call fee.

This service is **stateless** — it has no database. The NestJS side owns all order data and is responsible for storing resolved coordinates/Plus Codes on the order so re-optimization doesn't require re-geocoding. Do not add persistence to this service unless explicitly instructed.

---

## Tech stack

- **Python 3**, FastAPI, `pip` + `venv` (not Poetry/uv — team preference for setup simplicity)
- `httpx` for async HTTP calls to external APIs
- `pydantic` / `pydantic-settings` for schemas and config
- `ortools` for CP-SAT (zoning) and TSP-style solving (sequencing)
- No Docker yet — intentionally deferred until after the OR-Tools solver features are working locally (OR-Tools native bindings can be finicky in containers; better to containerize once the logic is proven). Revisit Docker once zoning + sequencing are both working.

## Project structure

```
routing-engine/
  app/
    api/         # FastAPI route definitions
    core/        # config.py (pydantic-settings)
    services/    # business logic calling external APIs (geocoding.py, matrix.py)
    models/      # Pydantic request/response schemas
    solvers/     # OR-Tools CP-SAT / TSP code — NOT YET BUILT, this is next
  tests/
  .env
  requirements.txt
  venv/
```

## Code conventions established so far (follow these patterns for new code)

- One concern per file: models in `app/models/`, external API clients in `app/services/`, HTTP routes in `app/api/`, solver logic will go in `app/solvers/`.
- Every new external-facing feature gets: a Pydantic request/response schema in `models/`, a service function that does the actual work, and a thin FastAPI router in `api/` that just calls the service and translates errors to HTTP.
- **Error handling pattern**: service functions raise/let bubble either `httpx.HTTPStatusError` (for APIs with real HTTP status codes, e.g. ORS) or a custom exception (for APIs that return HTTP 200 always with an error in the JSON body, e.g. Google — see `GoogleApiError` in `services/geocoding.py`). The API route layer catches these and maps to appropriate HTTP status codes (502 for upstream API failure/auth issues, 503 for rate limits/unreachable, 422 for bad input). A "no result found" (e.g. `ZERO_RESULTS`, empty ORS features list) is **not** an error — it's a normal successful response with a `null`/`None` result field.
- Batch endpoints (see `/geocode/batch`) use `asyncio.gather` with a `asyncio.Semaphore` to cap concurrency (currently 10 concurrent requests), and catch per-item exceptions so one bad item doesn't fail the whole batch — each item in the response carries either a success payload or an error string.
- GeoJSON-style APis (ORS) use `[longitude, latitude]` order — a common bug source, always double check.
- Google APIs (Places, and Distance-Matrix-style if ever used) return `lat`/`lng` as named fields, and return HTTP 200 even on failure — check the JSON `status` field, don't rely on `raise_for_status()` alone.

---

## What's already built (Phase 1 — Destination Identification, and Phase 2 — Distance Matrix)

### Phase 1: Destination identification

- `POST /geocode` — resolves a single place name / address (supports English and Khmer script) to lat/lng + Google Plus Code + confidence score + `needs_review` flag, via Google **Places API Text Search** (`place/textsearch/json`), not the plain Geocoding API — Places API handles landmark/place-name queries far better than structured-address geocoding, and natively returns a `plus_code` field.
- `POST /geocode/batch` — same, but accepts a list (`min_length=1, max_length=100`) and processes concurrently with the semaphore pattern described above.
- Key learnings baked into these decisions:
  - Mapbox was originally planned but **can't be billed from a Cambodia bank account** — do not reintroduce Mapbox without solving billing first.
  - ORS was tried for geocoding and found **inaccurate for Cambodia addresses** (thin OSM address-tagging in the region) — ORS is NOT used for geocoding, only for the distance matrix (see below), where the underlying road-network data is much more complete.
  - Google Plus Codes give more reliable results than free-text lat/lng lookups for Cambodia specifically, because informal/patchy street addressing means locals often share Plus Codes directly. The `plus_code` field is a first-class part of the geocode response.
  - AI (e.g. Gemini) was considered as a fallback for resolving place names the native pipeline can't find, but was explicitly **rejected as a primary/automatic fallback** — LLMs can hallucinate coordinates confidently with no "not found" signal, which is a dangerous failure mode for a system telling drivers where to physically go. If an AI fallback is ever added, it must only re-rank/disambiguate among real candidates already returned by an API — never generate a coordinate from scratch. Do not add an AI geocoding fallback unless explicitly instructed, and if you do, follow this constraint strictly.

### Phase 2: Distance matrix

- `POST /matrix` — takes a `starting_point` + list of `stops` (each with lat/lng), builds a combined `[starting_point, ...stops]` location list, and calls **ORS's Matrix endpoint** (`POST /v2/matrix/driving-car`) to get real road-network `distances_meters` and `durations_seconds` matrices covering all locations × all locations (not just starting-point-to-stops) — this single matrix is designed to feed both the zoning solver (needs stop-to-stop distances) and the later sequencing solver.
- ORS Matrix auth is a header (`Authorization: <key>`), unlike ORS Geocoding which used a query param — don't copy the wrong pattern.
- Free-tier ORS Matrix limit is ~3,500 elements; current schema caps `stops` at 49 (50 total locations = 2,500 elements) to stay safely under that. Revisit this ceiling once real batch sizes from production usage are known — do not silently raise it without checking real usage patterns first.

---

## What's left to build (in order)

### Phase 3: Zoning (OR-Tools CP-SAT)

- Owner specifies a **zone count** (independent of driver count).
- Input: the full distance matrix from Phase 2.
- OR-Tools **CP-SAT** solves for the best grouping of all destinations into that many zones, **minimizing total intra-zone travel distance** using the real road-distance matrix — this is a capacitated p-median/districting-style formulation, not straight-line k-means clustering.
- Output: N zones, each holding a subset of destination indices/labels.
- **Known risk to design for**: CP-SAT is an exact solver; solve time can grow significantly with stop count. Decide and implement a time-limit + best-found-solution fallback (CP-SAT can return a good incumbent solution even without proving optimality) rather than letting a solve hang indefinitely on a large batch. Pick a reasonable default time limit (e.g. a few seconds to low tens of seconds) and make it configurable.
- New files: `app/models/zoning.py`, `app/solvers/zoning.py` (the actual OR-Tools model-building code), `app/api/zoning.py`.

### Phase 4: Zone assignment

- This is a **human-in-the-loop step, not a solver feature** — the owner manually assigns each zone (output of Phase 3) to a driver. One driver can be assigned more than one zone in a shift.
- This is likely a thin pass-through / no computation needed on this service's side — confirm with the user whether this needs any endpoint here at all, or whether it's purely a NestJS/frontend concern (the Routing Engine may not need to do anything for this phase beyond returning zone contents from Phase 3 in a form the frontend can display for manual assignment). **Ask before building anything for this phase** — it may not require new code in this service.

### Phase 5: Per-zone sequencing (OR-Tools TSP)

- For each zone (now assigned to a driver), solve the TSP-style "best order to visit these stops" problem, starting from the driver's location.
- Driver preference — **outward-in** (farthest stop first) vs **inward-out** (nearest stop first) — is implemented as a **fixed-first-stop constraint** on this TSP solve, not a separate algorithm. Confirm with the user whether "driver's location" means a fixed depot/start point or a live GPS position at dispatch time — this affects whether the solve happens once at zone-assignment time or gets re-triggered per dispatch. This was flagged as an open question earlier and may not yet be resolved — ask before assuming.
- New files: `app/models/sequencing.py`, `app/solvers/sequencing.py`, `app/api/sequencing.py`.

### Phase 6: Per-leg navigation

- **No route geometry is generated or displayed in-app.** As the driver progresses through their sequence, generate a fresh "next stop only" deep link to Google Maps or Waze for just the next stop — this sidesteps the ~10-waypoint limit on consumer map apps entirely, since only one destination is ever sent at a time.
- Open questions flagged earlier, not yet resolved — ask the user before implementing:
  - What triggers advancing to the next stop? (Driver taps "arrived," vs. geofence-based auto-advance.)
  - What happens on a skipped/failed delivery? (Does it trigger re-sequencing of remaining stops, or just move to next-in-list?)
- New files: `app/models/navigation.py`, `app/services/navigation.py` (deep link generation is simple string building, likely no external API call needed), `app/api/navigation.py`.

---

## Working style instructions for you (the agent)

- Follow the **file-by-file** pattern already established: build and explain one complete file at a time, not line-by-line micro-steps, and not everything dumped at once.
- Before starting each new phase, briefly restate the plan for that phase and confirm any open design questions before writing code — several are flagged above as unresolved.
- Do not swap providers, add new dependencies, or change the stateless/no-DB architecture without flagging it clearly and getting confirmation first — several provider swaps already happened in this project (Mapbox → ORS → Google for geocoding) after real-world testing revealed problems, so treat current provider choices as tested and settled, not arbitrary.
- Keep error-handling and batch-processing conventions consistent with Phases 1–2 as described above.
