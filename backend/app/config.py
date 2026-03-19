from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    MONGO_URL: str
    MONGO_DB: str
    MONGO_PASSWORD: str

    MINIO_ENDPOINT: str
    MINIO_ROOT_USER: str
    MINIO_ROOT_PASSWORD: str
    MINIO_SECURE: bool
    MINIO_BUCKET: str
    MINIO_RAW_PREFIX: str
    MINIO_CLEAN_PREFIX: str
    MINIO_CURATED_PREFIX: str

    AIRFLOW_URL: str
    AIRFLOW_DAG_ID: str
    AIRFLOW_USERNAME: str
    AIRFLOW_PASSWORD: str

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_EXPIRE_MINUTES: int

    INSEE_BASE_URL: str
    INSEE_API_KEY: str

    model_config = SettingsConfigDict(
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
