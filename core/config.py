from pydantic_settings import BaseSettings, SettingsConfigDict
import os
from dotenv import load_dotenv

# 1. CARGAR EL ARCHIVO .ENV
load_dotenv()

# 2. LEER LAS VARIABLES
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

class Settings(BaseSettings):

    mongo_uri: str
    mongo_db_name: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:4321,http://127.0.0.1:4321,http://192.168.18.92:4321",
        ).split(",")
        if origin.strip()
    ]

settings = Settings()
