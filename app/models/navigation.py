from enum import Enum

from pydantic import BaseModel, Field


class NavigationApp(str, Enum):
    GOOGLE_MAPS = "google_maps"
    WAZE = "waze"


class NavigationPoint(BaseModel):
    latitude: float
    longitude: float


class NavigationRequest(BaseModel):
    app: NavigationApp = Field(
        default=NavigationApp.GOOGLE_MAPS,
        description="Navigation app to generate a deep link for",
    )
    start: NavigationPoint | None = Field(
        default=None,
        description="Driver's current location. Omitted for Google Maps to use the "
        "device's current position",
    )
    destination: NavigationPoint = Field(
        ..., description="The single next stop to navigate to"
    )
    destination_label: str | None = Field(
        default=None, description="Place name/hint for the destination"
    )


class NavigationResponse(BaseModel):
    app: NavigationApp
    deep_link: str = Field(
        ..., description="Deep link to open the next-stop navigation in the chosen app"
    )
    note: str | None = Field(
        default=None, description="Human-readable note about the link, if any"
    )
