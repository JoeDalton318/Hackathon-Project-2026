"""
storage/datalake.py
════════════════════
Data Lake MinIO — 3 zones : raw · clean · curated
"""
from __future__ import annotations
import io, json, logging, os
from datetime import datetime
from pathlib import Path
from typing import Optional

log     = logging.getLogger(__name__)
BUCKET  = "datalake"
ZONE_R, ZONE_C, ZONE_Q = "raw", "clean", "curated"
_client = None


def _get():
    global _client
    if _client is None:
        try:
            from minio import Minio
            c = Minio(os.getenv("MINIO_ENDPOINT", "localhost:9000"),
                      access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
                      secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin123"),
                      secure=os.getenv("MINIO_SECURE", "false").lower() == "true")
            if not c.bucket_exists(BUCKET): c.make_bucket(BUCKET)
            _client = c
        except Exception as e:
            log.warning(f"MinIO indisponible : {e}"); _client = False
    return None if _client is False else _client


def _key(zone, doc_id, name, ext):
    d = datetime.utcnow()
    return f"{zone}/{d.year}/{d.month:02d}/{d.day:02d}/{doc_id}/{name}.{ext}"


def _put(key, data, ct, meta):
    c = _get()
    if not c: return False
    try:
        c.put_object(BUCKET, key, io.BytesIO(data), len(data),
                     content_type=ct, metadata=meta)
        return True
    except Exception as e:
        log.error(f"Erreur PUT {key} : {e}"); return False


def store_raw(doc_id, file_bytes, file_name):
    ext = Path(file_name).suffix.lstrip(".") or "bin"
    key = _key(ZONE_R, doc_id, "original", ext)
    return key if _put(key, file_bytes,
                       "application/pdf" if ext == "pdf" else "image/jpeg",
                       {"document-id": doc_id, "original-filename": file_name}) else None


def store_clean(doc_id, raw_text, page_count, ocr_engine, ocr_confidence):
    payload = {"document_id": doc_id, "raw_text": raw_text, "page_count": page_count,
               "ocr_engine": ocr_engine, "ocr_confidence": ocr_confidence,
               "created_at": datetime.utcnow().isoformat()}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    key  = _key(ZONE_C, doc_id, "ocr_output", "json")
    return key if _put(key, data, "application/json", {"document-id": doc_id}) else None


def store_curated(doc_id, result):
    data = result.model_dump_json(indent=2).encode("utf-8")
    key  = _key(ZONE_Q, doc_id, "extraction", "json")
    return key if _put(key, data, "application/json",
                       {"document-id": doc_id,
                        "document-type": result.classification.document_type.value,
                        "overall-confidence": str(result.overall_confidence)}) else None


def list_curated(doc_type=None, limit=100):
    c = _get()
    if not c: return []
    try:
        results = []
        for i, obj in enumerate(c.list_objects(BUCKET, prefix=f"{ZONE_Q}/", recursive=True)):
            if i >= limit: break
            m = (c.stat_object(BUCKET, obj.object_name).metadata or {})
            e = {"key": obj.object_name,
                 "document_id":       m.get("x-amz-meta-document-id", ""),
                 "document_type":     m.get("x-amz-meta-document-type", ""),
                 "overall_confidence": float(m.get("x-amz-meta-overall-confidence", 0)),
                 "last_modified":     obj.last_modified.isoformat() if obj.last_modified else ""}
            if doc_type is None or e["document_type"] == doc_type:
                results.append(e)
        return results
    except Exception as e:
        log.error(f"Listing curated : {e}"); return []


def store_all_zones(file_bytes, file_name, result):
    doc_id = result.document_id
    return {
        ZONE_R: store_raw(doc_id, file_bytes, file_name),
        ZONE_C: store_clean(doc_id, result.raw_text,
                            result.ocr_metadata.page_count,
                            result.ocr_metadata.engine_used,
                            result.ocr_metadata.ocr_confidence_avg),
        ZONE_Q: store_curated(doc_id, result),
    }
