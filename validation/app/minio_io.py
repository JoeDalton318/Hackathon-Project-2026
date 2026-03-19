from __future__ import annotations

import io
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from minio import Minio

from .settings import settings


DEFAULT_BUCKET = settings.minio_bucket
DEFAULT_INPUT_PREFIX = settings.minio_clean_prefix
DEFAULT_OUTPUT_PREFIX = settings.minio_curated_prefix


@dataclass
class MinioJsonObject:
    object_name: str
    payload: Dict[str, Any]


class MinioIO:
    def __init__(
        self,
        endpoint: Optional[str] = None,
        access_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        secure: Optional[bool] = None,
        bucket: Optional[str] = None,
        input_prefix: Optional[str] = None,
        output_prefix: Optional[str] = None,
    ):
        self.endpoint = endpoint or settings.minio_endpoint
        self.access_key = access_key or settings.minio_access_key
        self.secret_key = secret_key or settings.minio_secret_key
        self.secure = secure if secure is not None else settings.minio_secure
        self.bucket = bucket or DEFAULT_BUCKET
        self.input_prefix = input_prefix or DEFAULT_INPUT_PREFIX
        self.output_prefix = output_prefix or DEFAULT_OUTPUT_PREFIX

        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure,
        )

    def list_input_json_objects(self) -> List[str]:
        objects: List[str] = []

        for obj in self.client.list_objects(self.bucket, prefix=self.input_prefix, recursive=True):
            object_name = obj.object_name.replace("\\", "/")

            if not object_name.endswith("/extraction.json"):
                continue

            objects.append(object_name)

        return sorted(objects)

    def read_json_object(self, object_name: str) -> Dict[str, Any]:
        response = self.client.get_object(self.bucket, object_name)
        try:
            data = response.read()
            return json.loads(data.decode("utf-8"))
        finally:
            response.close()
            response.release_conn()

    def load_payload_by_object_name(self, object_name: str) -> MinioJsonObject:
        normalized = object_name.replace("\\", "/")
        payload = self.read_json_object(normalized)
        return MinioJsonObject(object_name=normalized, payload=payload)

    def load_input_payloads(
        self,
        limit: Optional[int] = None,
        document_ids: Optional[List[str]] = None,
        file_names: Optional[List[str]] = None,
        object_names: Optional[List[str]] = None,
    ) -> List[MinioJsonObject]:
        if object_names:
            results: List[MinioJsonObject] = []
            for object_name in object_names:
                results.append(self.load_payload_by_object_name(object_name))
                if limit is not None and len(results) >= limit:
                    break
            return results

        all_object_names = self.list_input_json_objects()
        results: List[MinioJsonObject] = []

        wanted_ids = set(document_ids or [])
        wanted_files = set(file_names or [])

        for object_name in all_object_names:
            payload = self.read_json_object(object_name)

            payload_document_id = payload.get("document_id")
            payload_file_name = payload.get("file_name")

            if wanted_ids and payload_document_id not in wanted_ids:
                continue

            if wanted_files and payload_file_name not in wanted_files:
                continue

            results.append(MinioJsonObject(object_name=object_name, payload=payload))

            if limit is not None and len(results) >= limit:
                break

        return results

    def _put_json(
        self,
        object_name: str,
        payload: Dict[str, Any],
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

        self.client.put_object(
            self.bucket,
            object_name,
            io.BytesIO(data),
            length=len(data),
            content_type="application/json",
            metadata=metadata or {},
        )
        return object_name

    def store_batch_validation_result(self, batch_id: str, payload: Dict[str, Any]) -> str:
        now = datetime.now(timezone.utc)
        prefix = self.output_prefix.rstrip("/") + "/"
        object_name = (
            f"{prefix}"
            f"batches/{now.year}/{now.month:02d}/{now.day:02d}/"
            f"{batch_id}/validation_result.json"
        )

        metadata = {
            "result-type": "batch-validation",
            "batch-id": batch_id,
        }
        return self._put_json(object_name, payload, metadata)

    def store_document_validation_result(
        self,
        document_id: str,
        payload: Dict[str, Any],
        batch_id: Optional[str] = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        prefix = self.output_prefix.rstrip("/") + "/"
        object_name = (
            f"{prefix}"
            f"documents/{now.year}/{now.month:02d}/{now.day:02d}/"
            f"{document_id}/validation_result.json"
        )

        metadata = {
            "result-type": "document-validation",
            "document-id": document_id,
        }
        if batch_id:
            metadata["batch-id"] = batch_id

        return self._put_json(object_name, payload, metadata)