from pydantic_settings import BaseSettings

from pydantic import Field

class Settings(BaseSettings):
    groq_api_key: str = Field(alias="GROQ_API_KEY")
    sarvam_api_key: str = Field(alias="SARVAM_API_KEY")
    database_url: str = Field(alias="DATABASE_URL")

    class Config:
        env_file = ".env"

settings = Settings()