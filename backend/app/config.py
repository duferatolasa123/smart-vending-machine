
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"

class Settings(BaseSettings):
    app_name: str = "Smart Vending Machine API"
    environment: str = "development"

    database_url: str = (
        f"sqlite:///{(BACKEND_DIR / 'vending_machine.db').as_posix()}"
    )

    # Authentication settings
    secret_key: str = "CHANGE_THIS_DEVELOPMENT_SECRET_KEY"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    # Chapa payment settings
    chapa_secret_key: str = ""
    chapa_base_url: str = "https://api.chapa.co/v1"
    chapa_mode: str = "test"
    chapa_webhook_secret: str = ""
    frontend_origin: str = "http://localhost:5173"

    # Optional URLs. Configure these when the backend is publicly hosted.
    chapa_callback_url: str | None = None
    chapa_return_url: str | None = None
    # MCU command API. Configure this separately for the machine controller.
    mcu_api_token: str = ""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        if self.environment.lower() == "production":
            if (
                self.secret_key == "CHANGE_THIS_DEVELOPMENT_SECRET_KEY"
                or len(self.secret_key) < 32
            ):
                raise ValueError(
                    "Production SECRET_KEY must be a unique value of at least 32 characters."
                )
            if self.database_url.startswith("sqlite"):
                raise ValueError("Production must use a server database, not SQLite.")
            if self.chapa_mode.strip().lower() != "live":
                raise ValueError("Production requires CHAPA_MODE=live.")
            if (
                not self.chapa_secret_key.strip()
                or self.chapa_secret_key.startswith("CHASECK_TEST")
            ):
                raise ValueError("Production requires a live Chapa secret key.")
            if not self.chapa_webhook_secret.strip():
                raise ValueError("Production requires CHAPA_WEBHOOK_SECRET.")
            if len(self.chapa_webhook_secret.strip()) < 32:
                raise ValueError("Production CHAPA_WEBHOOK_SECRET must be at least 32 characters.")
            if len(self.mcu_api_token.strip()) < 32:
                raise ValueError("Production MCU_API_TOKEN must be at least 32 characters.")
            for name, value in (
                ("CHAPA_CALLBACK_URL", self.chapa_callback_url),
                ("CHAPA_RETURN_URL", self.chapa_return_url),
            ):
                if not value or not value.startswith("https://"):
                    raise ValueError(f"Production {name} must be an HTTPS URL.")
            if not self.frontend_origin.startswith("https://"):
                raise ValueError("Production FRONTEND_ORIGIN must use HTTPS.")

        if self.chapa_mode.strip().lower() not in {"test", "live"}:
            raise ValueError("CHAPA_MODE must be either 'test' or 'live'.")
        if (
            self.chapa_mode.strip().lower() == "live"
            and self.environment.strip().lower() != "production"
        ):
            raise ValueError("Live Chapa payments require ENVIRONMENT=production.")

        if self.access_token_expire_minutes <= 0:
            raise ValueError(
                "Access token expiration must be greater than zero."
            )

        return self

settings = Settings()
