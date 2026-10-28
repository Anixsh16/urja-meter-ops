from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    portal_url: str = "https://urja-ops.flockenergy.tech"
    portal_username: str = ""
    portal_password: SecretStr = SecretStr("")
    demo_api_key: SecretStr = SecretStr("")
    portal_timezone: str = "Asia/Kolkata"
    catalog_ttl: int = Field(300, ge=0, le=3600)
    energy_ttl: int = Field(60, ge=0, le=3600)
    cache_entries: int = Field(128, ge=1, le=1024)
    upstream_concurrency: int = Field(2, ge=1, le=4)
    web_dist: Path = Path("web/dist")

    @field_validator("portal_url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("PORTAL_URL must use HTTPS")
        return value.rstrip("/")

    @field_validator("portal_timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    def require_credentials(self) -> None:
        if not self.portal_username or not self.portal_password.get_secret_value():
            raise RuntimeError(
                "Set PORTAL_USERNAME and PORTAL_PASSWORD before starting the service"
            )
        if len(self.demo_api_key.get_secret_value()) < 24:
            raise RuntimeError("Set DEMO_API_KEY to a random token of at least 24 characters")
