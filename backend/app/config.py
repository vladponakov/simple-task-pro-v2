from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # peker på backend/.env
    model_config = SettingsConfigDict(
        env_file="backend/.env",
        env_file_encoding="utf-8",
    )

    # DB – lokalt sqlite, på Render bruker du DATABASE_URL env var
    DATABASE_URL: str = "sqlite:///./app.db"

    # CORS – lokalt + ev. prod-url senere
    CORS_ORIGINS: str | list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # ---- API-token for batch-kall fra Make.com ----
    # Brukes i X-API-Token header for:
    #  - /api/batch/import_students
    #  - /api/batch/import_daily
    #  - /api/batch/export_done
    API_TOKEN: str | None = "DEV_TOKEN_123"
    REQUIRE_API_TOKEN: bool = True

    # ---- Restore-vindu for soft delete (timer) ----
    RESTORE_WINDOW_HOURS: int = 24

    # ---- Make.com webhook for "DONE"-oppgaver ----
    # Når en oppgave settes til DONE i appen, kaller vi denne URL-en.
    MAKE_WEBHOOK_URL: str | None = None
    MAKE_WEBHOOK_API_KEY: str | None = None


settings = Settings()
