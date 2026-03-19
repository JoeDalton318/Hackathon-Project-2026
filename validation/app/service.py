from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from app.settings import settings
from app.anomaly_model import DocumentAnomalyModel
from app.insee_client import InseeClient
from app.minio_io import MinioIO
from app.ocr_adapter import load_ocr_batch_from_minio, load_ocr_batch_from_dir
from app.result_formatter import build_document_validation_results
from app.validation_engine import AnomalyEngine
from app.prepare_ml_data import generate_training_data, train_model

DEFAULT_MODEL_PATH = Path("artifacts") / "anomaly_model.joblib"


def load_ml_model(model_path: Path) -> DocumentAnomalyModel | None:
    if model_path.exists():
        return DocumentAnomalyModel.load(str(model_path))
    return None


def ensure_ml_model(model_path: Path) -> None:
    if model_path.exists():
        return
    print(f"[ML] Modèle absent : génération automatique dans {model_path}")
    generate_training_data()
    train_model()
    print("[ML] Modèle entraîné avec succès.")


def run_validation(
    *,
    source: str = "minio",
    batch_id: Optional[str] = None,
    limit: Optional[int] = None,
    extraction_keys: Optional[list[str]] = None,
    document_ids: Optional[list[str]] = None,
    file_names: Optional[list[str]] = None,
    input_dir: Optional[Path] = None,
    disable_insee: bool = False,
    disable_ml: bool = False,
    store_minio: bool = True,
    minio_endpoint: Optional[str] = None,
    minio_access_key: Optional[str] = None,
    minio_secret_key: Optional[str] = None,
    minio_secure: Optional[bool] = None,
    minio_bucket: Optional[str] = None,
    minio_prefix: Optional[str] = None,
    minio_validation_prefix: Optional[str] = None,
) -> dict:
    batch_id = batch_id or f"batch_validation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    resolved_secure = settings.minio_secure if minio_secure is None else minio_secure
    resolved_endpoint = minio_endpoint or settings.minio_endpoint
    resolved_access_key = minio_access_key or settings.minio_access_key
    resolved_secret_key = minio_secret_key or settings.minio_secret_key
    resolved_bucket = minio_bucket or settings.minio_bucket
    resolved_input_prefix = minio_prefix or settings.minio_clean_prefix
    resolved_output_prefix = minio_validation_prefix or settings.minio_curated_prefix

    if source == "dir":
        if not input_dir:
            raise ValueError("Avec source='dir', input_dir est obligatoire")

        batch = load_ocr_batch_from_dir(
            input_dir=input_dir,
            batch_id=batch_id,
            limit=limit,
            document_ids=document_ids,
            file_names=file_names,
        )
    else:
        batch = load_ocr_batch_from_minio(
            batch_id=batch_id,
            limit=limit,
            document_ids=document_ids,
            file_names=file_names,
            object_names=extraction_keys,
            endpoint=resolved_endpoint,
            access_key=resolved_access_key,
            secret_key=resolved_secret_key,
            secure=resolved_secure,
            bucket=resolved_bucket,
            prefix=resolved_input_prefix,
        )

    if disable_ml:
        anomaly_model = None
    else:
        ensure_ml_model(DEFAULT_MODEL_PATH)
        anomaly_model = load_ml_model(DEFAULT_MODEL_PATH)

    if disable_insee:
        insee_client = InseeClient(enabled=False, fallback_to_mock=False)
    else:
        insee_client = InseeClient(enabled=True, fallback_to_mock=True)

    engine = AnomalyEngine(
        insee_client=insee_client,
        anomaly_model=anomaly_model,
        reference_date=datetime.utcnow(),
        engine_version="1.2.0",
    )

    result = engine.run(batch)
    per_document_results = build_document_validation_results(result, batch)

    stored = {"batch": None, "documents": []}

    if store_minio:
        io_client = MinioIO(
            endpoint=resolved_endpoint,
            access_key=resolved_access_key,
            secret_key=resolved_secret_key,
            secure=resolved_secure,
            bucket=resolved_bucket,
            input_prefix=resolved_input_prefix,
            output_prefix=resolved_output_prefix,
        )

        stored["batch"] = io_client.store_batch_validation_result(
            batch_id=result.batch_id,
            payload=result.model_dump(),
        )

        for doc_payload in per_document_results:
            doc_key = io_client.store_document_validation_result(
                document_id=doc_payload["document_id"],
                payload=doc_payload,
                batch_id=result.batch_id,
            )
            stored["documents"].append(doc_key)

    return {
        "batch_result": result.model_dump(),
        "document_results": per_document_results,
        "stored": stored,
    }