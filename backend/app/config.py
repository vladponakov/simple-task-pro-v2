from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    CORS_ORIGINS: str = "*"
    RESTORE_WINDOW_HOURS: int = 24

settings = Settings()
