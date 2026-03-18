from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    minio_endpoint: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    minio_access_key: str = os.getenv("MINIO_ACCESS_KEY", "")
    minio_secret_key: str = os.getenv("MINIO_SECRET_KEY", "")
    minio_secure: bool = _as_bool(os.getenv("MINIO_SECURE"), False)
    minio_bucket: str = os.getenv("MINIO_BUCKET", "datalake")
    minio_curated_prefix: str = os.getenv("MINIO_CURATED_PREFIX", "curated/")
    minio_validation_prefix: str = os.getenv("MINIO_VALIDATION_PREFIX", "curated/validation/")

    insee_base_url: str = os.getenv("INSEE_BASE_URL", "https://api.insee.fr/api-sirene/3.11")
    insee_api_key: str = os.getenv("INSEE_API_KEY", "")


settings = Settings()