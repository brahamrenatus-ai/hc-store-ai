"""Konfigurasi aplikasi berbasis Pydantic Settings."""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Pengaturan layanan HC Store AI dari variabel lingkungan."""

    service_api_key: SecretStr
    gemini_api_key: SecretStr | None = None
    app_timezone: str = "Asia/Makassar"
    docs_enabled: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @field_validator("service_api_key")
    @classmethod
    def validate_service_api_key(cls, v: SecretStr) -> SecretStr:
        """Memastikan panjang kunci layanan minimal 16 karakter."""
        if len(v.get_secret_value()) < 16:
            raise ValueError("Kunci layanan minimal 16 karakter.")
        return v

    @field_validator("app_timezone")
    @classmethod
    def validate_app_timezone(cls, v: str) -> str:
        """Memastikan zona waktu terdaftar dalam basis data zona waktu IANA."""
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"Zona waktu bukan zona IANA yang valid: {v}") from exc
        return v

    @property
    def provider_configured(self) -> bool:
        """Menunjukkan apakah kunci API penyedia LLM telah terkonfigurasi."""
        if self.gemini_api_key is None:
            return False
        return bool(self.gemini_api_key.get_secret_value().strip())
