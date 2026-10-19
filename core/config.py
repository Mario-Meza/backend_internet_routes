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




settings = Settings()