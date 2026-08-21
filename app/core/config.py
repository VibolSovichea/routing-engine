from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ors_api_key: str | None = None
    ors_base_url: str = "https://api.openrouteservice.org"

    mapbox_access_token: str | None = None
    google_maps_api_key: str | None = None
    geocode_provider: str | None = None

    default_country_code: str = "KH"


settings = Settings()
