"""

Data Lake MinIO — 3 étapes logiques

raw/     → document original
clean/   → extraction OCR structurée (extraction.json)
curated/ → résultats finaux validation
"""
from __future__ import annotations

import io, json, logging, os
from datetime import datetime
from pathlib import Path
from typing import Optional

log     = logging.getLogger(__name__)
BUCKET  = "datalake"

ZONE_RAW     = "raw"
ZONE_CLEAN   = "clean"
ZONE_CURATED = "curated"

_client = None


def _get():
    global _client
    if _client is None:
        try:
            from minio import Minio
            c = Minio(
                os.getenv("MINIO_ENDPOINT", "localhost:9000"),
                access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
                secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
                secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
            )
            if not c.bucket_exists(BUCKET):
                c.make_bucket(BUCKET)
            _client = c
        except Exception as e:
            log.warning(f"MinIO indisponible : {e}")
            _client = False
    return None if _client is False else _client


def _key(zone: str, doc_id: str, name: str, ext: str) -> str:
    d = datetime.utcnow()
    return f"{zone}/{d.year}/{d.month:02d}/{d.day:02d}/{doc_id}/{name}.{ext}"


def _put(key: str, data: bytes, content_type: str, meta: dict) -> bool:
    c = _get()
    if not c:
        return False
    try:
        c.put_object(
            BUCKET, key,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
            metadata=meta,
        )
        return True
    except Exception as e:
        log.error(f"Erreur PUT {key} : {e}")
        return False


# ─── RAW ────────────────────────────────────────────

def store_raw_document(doc_id: str, file_bytes: bytes, file_name: str) -> Optional[str]:
    ext = Path(file_name).suffix.lstrip(".") or "bin"
    ct  = "application/pdf" if ext == "pdf" else "image/jpeg"
    key = _key(ZONE_RAW, doc_id, "original", ext)
    return key if _put(key, file_bytes, ct, {
        "document-id": doc_id,
        "original-filename": file_name,
    }) else None


def store_raw_extraction(doc_id: str, extraction_result) -> Optional[str]:
    data = extraction_result.model_dump_json(indent=2).encode("utf-8")
    key  = _key(ZONE_CLEAN, doc_id, "extraction", "json")
    return key if _put(key, data, "application/json", {
        "document-id": doc_id,
        "document-type": extraction_result.classification.document_type.value,
        "overall-confidence": str(extraction_result.overall_confidence),
    }) else None

# ─── CLEAN ─────────────────────────────────────────

def store_clean(
    doc_id: str,
    raw_text: str,
    page_count: int,
    ocr_engine: str,
    ocr_confidence: float,
) -> Optional[str]:
    payload = {
        "document_id": doc_id,
        "raw_text": raw_text,
        "page_count": page_count,
        "ocr_engine": ocr_engine,
        "ocr_confidence": ocr_confidence,
        "created_at": datetime.utcnow().isoformat(),
    }
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    key  = _key(ZONE_CLEAN, doc_id, "ocr_text", "json")
    return key if _put(key, data, "application/json", {
        "document-id": doc_id,
    }) else None


# ─── CURATED ───────────────────────────────

def store_curated(doc_id: str, result) -> Optional[str]:
    return None
    
# ─── API principale ───────────────────────────────

def store_all_zones(file_bytes, file_name, extraction_result):
    doc_id = extraction_result.document_id

    return {
        "raw_document":   store_raw_document(doc_id, file_bytes, file_name),
        "raw_extraction": store_raw_extraction(doc_id, extraction_result),
        "clean":          store_clean(
            doc_id,
            extraction_result.raw_text,
            extraction_result.ocr_metadata.page_count,
            extraction_result.ocr_metadata.engine_used,
            extraction_result.ocr_metadata.ocr_confidence_avg,
        ),
        "curated":        None,
    }