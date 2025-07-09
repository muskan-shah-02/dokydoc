import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """
    Application settings, loaded from environment variables.
    """
    # --- Project Settings ---
    PROJECT_NAME: str = "DokyDoc"

    # --- Database Settings ---
    # The URL for connecting to the PostgreSQL database.
    # It will be read from the environment variable set in docker-compose.yml
    DATABASE_URL: str

    # --- JWT Settings ---
    SECRET_KEY: str = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    #-----Gemini API Settings-----
    GEMINI_API_KEY: str = "AIzaSyD22VeU2AodTHfMtMO1YfbPisTrAiyjJgs"

    class Config:
        # Pydantic will automatically look for environment variables
        # and a .env file if it exists.
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()
