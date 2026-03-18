from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)


class Settings(BaseSettings):
    MONGO_URL: str
    MONGO_DB: str
    MONGO_PASSWORD: str

    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_SECURE: bool
    MINIO_BUCKET: str
    MINIO_CURATED_PREFIX: str
    MINIO_VALIDATION_PREFIX: str

    AIRFLOW_URL: str
    AIRFLOW_DAG_ID: str
    AIRFLOW_USERNAME: str
    AIRFLOW_PASSWORD: str

    INTERNAL_API_SECRET: str

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_EXPIRE_MINUTES: int

    INSEE_BASE_URL: str
    INSEE_API_KEY: str

    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8")


settings = Settings()
