from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    debug: bool = False

    # OpenAI Configuration (required for deep_researcher)
    openai_api_key: str = ""
    
    # Anthropic Configuration (optional, for Claude models)
    anthropic_api_key: str = ""
    
    # Tavily Configuration (optional, for web search)
    tavily_api_key: str = ""
    
    # Default model settings
    default_model: str = "gpt-4o"
    default_max_research_iterations: int = 6

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    allowed_origins: str = "*"

    @property
    def origins_list(self) -> List[str]:
        """Return allowed origins as a list"""
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
