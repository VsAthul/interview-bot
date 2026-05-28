from pydantic_settings import BaseSettings, SettingsConfigDict

from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", populate_by_name=True)

    groq_api_key: str = Field(alias="GROQ_API_KEY")
    sarvam_api_key: str = Field(alias="SARVAM_API_KEY")
    database_url: str = Field(alias="DATABASE_URL")

settings = Settings()

max_questions = 7