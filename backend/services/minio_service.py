import io
from datetime import timedelta
from uuid import uuid4

from minio import Minio

from app.config import settings
from database.minio import get_minio


def _batch_id() -> str:
    return f"batch_{uuid4().hex[:12]}"


async def upload_raw(
    user_id: str,
    document_id: str,
    filename: str,
    data: bytes,
    content_type: str,
    batch_id: str | None = None,
) -> str:
    """Stocke le fichier brut en Bronze (data-architecture: bronze/uploads/{user_id}/{batch_id}/{filename})."""
    client: Minio = get_minio()
    batch = batch_id or _batch_id()
    object_name = f"bronze/uploads/{user_id}/{batch}/{filename}"
    client.put_object(
        bucket_name=settings.MINIO_BUCKET_RAW,
        object_name=object_name,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_name


def get_presigned_url(object_name: str, expires_minutes: int = 15) -> str:
    client: Minio = get_minio()
    return client.presigned_get_object(
        bucket_name=settings.MINIO_BUCKET_RAW,
        object_name=object_name,
        expires=timedelta(minutes=expires_minutes),
    )
