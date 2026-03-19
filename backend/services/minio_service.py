import io
from datetime import timedelta

from minio import Minio

from app.config import settings
from database.minio import get_minio


async def upload_raw(
    document_id: str, filename: str, data: bytes, content_type: str
) -> str:
    client = get_minio()
    object_name = f"{settings.MINIO_RAW_PREFIX}{document_id}/{filename}"
    client.put_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=object_name,
        data=io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return object_name


def get_presigned_url(object_name: str, expires_minutes: int = 15) -> str:
    client = get_minio()
    return client.presigned_get_object(
        bucket_name=settings.MINIO_BUCKET,
        object_name=object_name,
        expires=timedelta(minutes=expires_minutes),
    )
