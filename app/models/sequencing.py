from enum import Enum

from pydantic import BaseModel, Field


class DriverPreference(str, Enum):
    OUTWARD_IN = "outward_in"
    INWARD_OUT = "inward_out"


class StartPoint(BaseModel):
    label: str = Field(
        ..., description="Identifier for the driver's current location"
    )
    latitude: float
    longitude: float


class SequencingStop(BaseModel):
    label: str = Field(
        ..., description="Identifier for this stop, e.g. order ID or name"
    )
    latitude: float
    longitude: float


class SequencingRequest(BaseModel):
    start_point: StartPoint = Field(
        ..., description="Driver's live location to start from"
    )
    stops: list[SequencingStop] = Field(
        ..., min_length=2, max_length=49, description="Stops to sequence"
    )
    distances_meters: list[list[float]] = Field(
        ...,
        description="(N+1) x (N+1) symmetric distance matrix (meters); index 0 is the start point, "
        "indices 1..N are the stops in order",
    )
    durations_seconds: list[list[float]] | None = Field(
        default=None,
        description="Optional (N+1) x (N+1) symmetric duration matrix (seconds) in the same "
        "layout, used for reporting leg/route durations",
    )
    driver_preference: DriverPreference = Field(
        default=DriverPreference.OUTWARD_IN,
        description="Whether to start with the farthest stop (outward-in) or nearest stop (inward-out)",
    )


class SequencingLeg(BaseModel):
    from_label: str = Field(
        ..., description="Label of the origin of this leg"
    )
    to_label: str = Field(..., description="Label of the destination of this leg")
    distance_meters: float
    duration_seconds: float | None = Field(
        default=None, description="Driving duration for this leg, if durations were provided"
    )


class SequencingResponse(BaseModel):
    start_point: StartPoint
    stops_order: list[SequencingStop] = Field(
        ..., description="Stops in the optimal visit order (first stop is the fixed first stop)"
    )
    labels_order: list[str] = Field(
        ..., description="Labels of stops in visit order"
    )
    legs: list[SequencingLeg] = Field(
        ..., description="Driving legs from the start point through the stops"
    )
    total_distance_meters: float
    total_duration_seconds: float | None = Field(
        default=None, description="Total driving duration, if durations were provided"
    )
    solver_status: str = Field(
        ..., description="Solver termination status (e.g. OPTIMAL, FEASIBLE, INFEASIBLE)"
    )
    solver_time_seconds: float = Field(
        ..., description="Wall-clock time the solver ran"
    )
