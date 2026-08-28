from pydantic import BaseModel, Field


class ZoningLocation(BaseModel):
    label: str = Field(
        ..., description="Identifier for this stop, e.g. order ID or name"
    )
    latitude: float
    longitude: float


class ZoneGroup(BaseModel):
    zone_id: int = Field(..., ge=0, description="Zero-based zone index")
    location_indices: list[int] = Field(
        ..., description="Indices of locations assigned to this zone"
    )
    locations: list[ZoningLocation] = Field(
        ..., description="Location details for this zone's assignments"
    )
    intra_zone_distance_meters: float = Field(
        ...,
        description="Sum of pairwise distances between all stops in this zone",
    )


class ZoningRequest(BaseModel):
    zone_count: int = Field(
        ..., ge=2, le=20, description="Number of zones to create"
    )
    locations: list[ZoningLocation] = Field(
        ..., min_length=2, max_length=50, description="All stops to zone"
    )
    distances_meters: list[list[float]] = Field(
        ...,
        description="N x N symmetric distance matrix (meters) in the same order as locations",
    )


class ZoningResponse(BaseModel):
    zones: list[ZoneGroup]
    solver_status: str = Field(
        ..., description="Solver termination status (e.g. OPTIMAL, FEASIBLE, INFEASIBLE)"
    )
    solver_time_seconds: float = Field(
        ..., description="Wall-clock time the solver ran"
    )
