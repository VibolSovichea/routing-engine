"""Application configuration loaded from environment variables / .env."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings for the routing engine."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # OpenRouteService (routing / matrix)
    ors_api_key: str | None = None
    ors_base_url: str = "https://api.openrouteservice.org"

    # Geocoding providers
    mapbox_access_token: str | None = None
    google_maps_api_key: str | None = None
    geocode_provider: str | None = None

    # Defaults
    default_country_code: str = "KH"

    # Solver defaults
    zone_time_limit_seconds: float = 10.0


settings = Settings()
