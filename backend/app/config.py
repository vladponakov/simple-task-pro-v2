from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # peker på backend/.env
    model_config = SettingsConfigDict(env_file='backend/.env', env_file_encoding='utf-8')

    DATABASE_URL: str = "sqlite:///./app.db"
    CORS_ORIGINS: str | list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    API_TOKENS: list[str] = ["DEV_TOKEN_123"]
    REQUIRE_API_TOKEN: bool = True  # settes til false i backend/.env for dev

settings = Settings()
