from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="forbid",
        env_file_encoding="utf-8",
    )

    ors_api_key: str | None = None
    ors_base_url: str = "https://api.openrouteservice.org"

    mapbox_access_token: str | None = None
    google_maps_api_key: str | None = None
    geocode_provider: str | None = None

    service_api_key: str | None = None

    default_country_code: str = "KH"

    zone_time_limit_seconds: float = 10.0
    sequence_time_limit_seconds: float = 5.0

    log_level: str = "INFO"
    log_format: str = "json"

    def required_keys(self) -> list[str]:
        missing: list[str] = []
        if not self.ors_api_key:
            missing.append("ORS_API_KEY")
        if not self.google_maps_api_key:
            missing.append("GOOGLE_MAPS_API_KEY")
        if not self.service_api_key:
            missing.append("SERVICE_API_KEY")
        return missing


@lru_cache
def get_settings() -> Settings:
    return Settings()


def validate_startup(settings: Settings) -> None:
    missing = settings.required_keys()
    if missing:
        raise RuntimeError(
            "Routing Engine configuration is incomplete. Missing required "
            f"environment variable(s): {', '.join(missing)}. "
            "Set them in .env (see .env.example) before starting."
        )
