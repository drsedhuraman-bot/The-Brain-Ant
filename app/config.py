from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    model: str = "claude-sonnet-4-6"
    max_ant_concurrency: int = 3
    task_timeout_seconds: int = 120

    class Config:
        env_file = ".env"


settings = Settings()
