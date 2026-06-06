from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str = "mock-key"
    supabase_url: str = "https://mock.supabase.co"
    supabase_anon_key: str = "mock-anon"
    supabase_service_role_key: str = "mock-service-role"
    database_type: str = "sqlite"  # "sqlite" or "supabase"
    sqlite_db_path: str = "brain_ant.db"
    model: str = "claude-sonnet-4-6"
    max_ant_concurrency: int = 3
    task_timeout_seconds: int = 120

    class Config:
        env_file = ".env"


settings = Settings()

# Automatically determine database type based on settings
if settings.supabase_url != "https://mock.supabase.co" and settings.supabase_url:
    settings.database_type = "supabase"
else:
    settings.database_type = "sqlite"

