from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "CAMPUSINTEL API"
    database_url: str = "postgresql+psycopg://campusintel:local-development-only-change-me@localhost:5432/campusintel"
    backend_cors_origins: str = "http://localhost:5173"
    jwt_secret: str = "replace-this-development-secret-before-deployment"
    jwt_expire_minutes: int = 60
    upload_directory: str = "private_uploads"
    max_upload_bytes: int = 5_000_000
    classification_model_path: str = ".models/category_classifier.joblib"
    semantic_model_path: str = ".models/category_semantic_classifier.joblib"
    embedding_model_path: str = ""
    resolution_model_path: str = ".models/resolution_predictor.joblib"
    frontend_public_url: str = "http://localhost:5173"
    smtp_host: str = ""
    smtp_port: int = 1025
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = False
    smtp_use_ssl: bool = False
    smtp_from_email: str = ""
    smtp_from_name: str = "CAMPUSINTEL"
    password_reset_expire_minutes: int = 30

    @property
    def password_reset_email_configured(self) -> bool:
        return bool(self.smtp_host.strip() and self.smtp_from_email.strip())

    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
