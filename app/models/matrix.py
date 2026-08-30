from pydantic import BaseModel, Field


class MatrixLocation(BaseModel):
    label: str = Field(
        ..., description="Identifier for this stop, e.g. order ID or name"
    )
    latitude: float
    longitude: float


class MatrixRequest(BaseModel):
    starting_point: MatrixLocation
    stops: list[MatrixLocation] = Field(..., min_length=1, max_length=49)


class DistanceMatrixResponse(BaseModel):
    locations: list[MatrixLocation]
    distances_meters: list[list[float]]
    durations_seconds: list[list[float]]
