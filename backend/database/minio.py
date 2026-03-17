from minio import Minio

from app.config import settings

_client: Minio | None = None


def get_minio() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _client


def init_buckets() -> None:
    """Crée les buckets Bronze / Silver / Gold (data-architecture)."""
    client = get_minio()
    for bucket in [
        settings.MINIO_BUCKET_RAW,
        settings.MINIO_BUCKET_CLEAN,
        settings.MINIO_BUCKET_CURATED,
    ]:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
