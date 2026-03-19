"""
storage/datalake.py
════════════════════
<<<<<<< HEAD
Data Lake MinIO — 2 zones, que Juba gère :

  raw/    → document original (PDF/image) + résultat d'extraction OCR (JSON)
  clean/  → texte OCR brut

  curated/ → géré par Maria 
"""
from __future__ import annotations

=======
Data Lake MinIO — 3 zones : raw · clean · curated
"""
from __future__ import annotations
>>>>>>> origin/maria
import io, json, logging, os
from datetime import datetime
from pathlib import Path
from typing import Optional

log     = logging.getLogger(__name__)
BUCKET  = "datalake"
<<<<<<< HEAD
ZONE_RAW   = "raw"
ZONE_CLEAN = "clean"
# ZONE_CURATED → géré par Maria

=======
ZONE_R, ZONE_C, ZONE_Q = "raw", "clean", "curated"
>>>>>>> origin/maria
_client = None


def _get():
    global _client
    if _client is None:
        try:
            from minio import Minio
<<<<<<< HEAD
            c = Minio(
                os.getenv("MINIO_ENDPOINT",   "localhost:9000"),
                access_key=os.getenv("MINIO_ACCESS_KEY", ""),
                secret_key=os.getenv("MINIO_SECRET_KEY", ""),
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
=======
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
>>>>>>> origin/maria
    d = datetime.utcnow()
    return f"{zone}/{d.year}/{d.month:02d}/{d.day:02d}/{doc_id}/{name}.{ext}"


<<<<<<< HEAD
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
        log.debug(f"Stocké : {key}")
        return True
    except Exception as e:
        log.error(f"Erreur PUT {key} : {e}")
        return False


# ─── Zone RAW : document original ────────────────────────────────────────────

def store_raw_document(doc_id: str, file_bytes: bytes, file_name: str) -> Optional[str]:
    """Stocke le document original brut (PDF/image) dans la zone RAW."""
    ext = Path(file_name).suffix.lstrip(".") or "bin"
    ct  = "application/pdf" if ext == "pdf" else "image/jpeg"
    key = _key(ZONE_RAW, doc_id, "original", ext)
    ok  = _put(key, file_bytes, ct, {
        "document-id":       doc_id,
        "original-filename": file_name,
        "zone":              "raw",
        "content":           "original_document",
        "uploaded-at":       datetime.utcnow().isoformat(),
    })
    return key if ok else None


def store_raw_extraction(doc_id: str, extraction_result) -> Optional[str]:
    """
    Stocke le résultat d'extraction OCR (JSON) dans la zone RAW.
    C'est l'extraction brute avant validation — la Curated zone
    sera alimentée par l'équipe Validation.
    """
    data = extraction_result.model_dump_json(indent=2).encode("utf-8")
    key  = _key(ZONE_RAW, doc_id, "extraction_ocr", "json")
    ok   = _put(key, data, "application/json", {
        "document-id":       doc_id,
        "document-type":     extraction_result.classification.document_type.value,
        "overall-confidence": str(extraction_result.overall_confidence),
        "zone":              "raw",
        "content":           "ocr_extraction",
        "extracted-at":      datetime.utcnow().isoformat(),
    })
    return key if ok else None


# ─── Zone CLEAN : texte OCR brut ─────────────────────────────────────────────

def store_clean(
    doc_id:         str,
    raw_text:       str,
    page_count:     int,
    ocr_engine:     str,
    ocr_confidence: float,
) -> Optional[str]:
    """Stocke le texte OCR brut dans la zone CLEAN."""
    payload = {
        "document_id":    doc_id,
        "raw_text":       raw_text,
        "page_count":     page_count,
        "ocr_engine":     ocr_engine,
        "ocr_confidence": ocr_confidence,
        "created_at":     datetime.utcnow().isoformat(),
    }
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    key  = _key(ZONE_CLEAN, doc_id, "ocr_text", "json")
    ok   = _put(key, data, "application/json", {
        "document-id": doc_id,
        "zone":        "clean",
        "content":     "ocr_text",
    })
    return key if ok else None


# ─── API principale ───────────────────────────────────────────────────────────

def store_all_zones(
    file_bytes: bytes,
    file_name:  str,
    extraction_result,
) -> dict[str, Optional[str]]:
    """
    Écrit dans les zones gérées par Juba (RAW + CLEAN).
    La zone CURATED est gérée par Maria.

    Retourne :
        {
          "raw_document":  "raw/.../original.pdf",
          "raw_extraction": "raw/.../extraction_ocr.json",
          "clean":         "clean/.../ocr_text.json",
        }
    """
    doc_id = extraction_result.document_id

    raw_doc = store_raw_document(doc_id, file_bytes, file_name)

    raw_ext = store_raw_extraction(doc_id, extraction_result)

    clean = store_clean(
        doc_id,
        raw_text       = extraction_result.raw_text,
        page_count     = extraction_result.ocr_metadata.page_count,
        ocr_engine     = extraction_result.ocr_metadata.engine_used,
        ocr_confidence = extraction_result.ocr_metadata.ocr_confidence_avg,
    )

    keys = {
        "raw_document":   raw_doc,
        "raw_extraction": raw_ext,
        "clean":          clean,
    }

    log.info(
        f"[{doc_id}] Stockage terminé → "
        f"raw_doc={'OK' if raw_doc else 'KO'} | "
        f"raw_extraction={'OK' if raw_ext else 'KO'} | "
        f"clean={'OK' if clean else 'KO'}"
    )

    return keys


def list_raw_extractions(limit: int = 100) -> list[dict]:
    """
    Liste les extractions OCR stockées dans la zone RAW.
    Utilisé par l'équipe Validation pour récupérer les données à traiter.
    """
    c = _get()
    if not c:
        return []
    try:
        results = []
        for i, obj in enumerate(
            c.list_objects(BUCKET, prefix=f"{ZONE_RAW}/", recursive=True)
        ):
            if i >= limit:
                break
            if not obj.object_name.endswith("extraction_ocr.json"):
                continue
            stat = c.stat_object(BUCKET, obj.object_name)
            m    = stat.metadata or {}
            results.append({
                "key":               obj.object_name,
                "document_id":       m.get("x-amz-meta-document-id", ""),
                "document_type":     m.get("x-amz-meta-document-type", ""),
                "overall_confidence": float(m.get("x-amz-meta-overall-confidence", 0)),
                "extracted_at":      m.get("x-amz-meta-extracted-at", ""),
                "last_modified":     obj.last_modified.isoformat() if obj.last_modified else "",
            })
        return results
    except Exception as e:
        log.error(f"Listing raw extractions : {e}")
        return []
=======
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
>>>>>>> origin/maria
