from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validation des JSON OCR stockés dans MinIO"
    )

    parser.add_argument("--batch-id", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)

    parser.add_argument(
        "--document-id",
        action="append",
        default=None,
        help="Filtrer sur un ou plusieurs document_id",
    )
    parser.add_argument(
        "--file-name",
        action="append",
        default=None,
        help="Filtrer sur un ou plusieurs file_name",
    )

    parser.add_argument(
        "--input-dir",
        type=str,
        default=None,
        help="Dossier local contenant des JSON OCR à valider",
    )
    parser.add_argument(
        "--source",
        choices=["minio", "dir"],
        default="minio",
        help="Source d'entrée des JSON OCR",
    )

    parser.add_argument("--minio-endpoint", type=str, default=settings.minio_endpoint)
    parser.add_argument("--minio-access-key", type=str, default=settings.minio_access_key)
    parser.add_argument("--minio-secret-key", type=str, default=settings.minio_secret_key)
    parser.add_argument("--minio-secure", action="store_true", default=settings.minio_secure)
    parser.add_argument("--minio-bucket", type=str, default=settings.minio_bucket)
    parser.add_argument("--minio-prefix", type=str, default=settings.minio_curated_prefix)
    parser.add_argument("--minio-validation-prefix", type=str, default=settings.minio_validation_prefix)

    parser.add_argument(
        "--disable-insee",
        action="store_true",
        help="Désactive la vérification INSEE",
    )
    parser.add_argument(
        "--disable-ml",
        action="store_true",
        help="Désactive le modèle ML",
    )
    parser.add_argument(
        "--no-store-minio",
        dest="store_minio",
        action="store_false",
        help="Désactive l'écriture des résultats dans MinIO",
    )
    parser.set_defaults(store_minio=True)

    args = parser.parse_args()

    batch_id = args.batch_id or f"batch_validation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

    if args.source == "dir":
        if not args.input_dir:
            raise ValueError("Avec --source dir, il faut fournir --input-dir")
        batch = load_ocr_batch_from_dir(
            input_dir=Path(args.input_dir),
            batch_id=batch_id,
            limit=args.limit,
            document_ids=args.document_id,
            file_names=args.file_name,
        )
    else:
        batch = load_ocr_batch_from_minio(
            batch_id=batch_id,
            limit=args.limit,
            document_ids=args.document_id,
            file_names=args.file_name,
            endpoint=args.minio_endpoint,
            access_key=args.minio_access_key,
            secret_key=args.minio_secret_key,
            secure=args.minio_secure,
            bucket=args.minio_bucket,
            prefix=args.minio_prefix,
        )

    if args.disable_ml:
        anomaly_model = None
    else:
        ensure_ml_model(DEFAULT_MODEL_PATH)
        anomaly_model = load_ml_model(DEFAULT_MODEL_PATH)

    if args.disable_insee:
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

    print("\n===== VALIDATION RESULT =====\n")
    print(result.model_dump_json(indent=2, ensure_ascii=False))

    per_document_results = build_document_validation_results(result, batch)

    if args.store_minio:
        io_client = MinioIO(
            endpoint=args.minio_endpoint,
            access_key=args.minio_access_key,
            secret_key=args.minio_secret_key,
            secure=args.minio_secure,
            bucket=args.minio_bucket,
            input_prefix=args.minio_prefix,
            validation_prefix=args.minio_validation_prefix,
        )

        batch_key = io_client.store_batch_validation_result(
            batch_id=result.batch_id,
            payload=result.model_dump(),
        )
        print(f"Résultat batch stocké dans MinIO : {batch_key}")

        for doc_payload in per_document_results:
            doc_key = io_client.store_document_validation_result(
                document_id=doc_payload["document_id"],
                payload=doc_payload,
                batch_id=result.batch_id,
            )
            print(f"Résultat document stocké dans MinIO : {doc_key}")
    else:
        print("Écriture MinIO désactivée.")


if __name__ == "__main__":
    main()