from __future__ import annotations

import argparse
from pathlib import Path

from app.settings import settings
from app.service import run_validation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validation des JSON OCR stockés dans MinIO"
    )

    parser.add_argument("--batch-id", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)

    parser.add_argument(
        "--extraction-key",
        action="append",
        default=None,
        help="Clé MinIO exacte de l'extraction à valider. Peut être répétée.",
    )
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

    result = run_validation(
        source=args.source,
        batch_id=args.batch_id,
        limit=args.limit,
        extraction_keys=args.extraction_key,
        document_ids=args.document_id,
        file_names=args.file_name,
        input_dir=Path(args.input_dir) if args.input_dir else None,
        disable_insee=args.disable_insee,
        disable_ml=args.disable_ml,
        store_minio=args.store_minio,
        minio_endpoint=args.minio_endpoint,
        minio_access_key=args.minio_access_key,
        minio_secret_key=args.minio_secret_key,
        minio_secure=args.minio_secure,
        minio_bucket=args.minio_bucket,
        minio_prefix=args.minio_prefix,
        minio_validation_prefix=args.minio_validation_prefix,
    )

    print("\n===== VALIDATION RESULT =====\n")
    print(result["batch_result"])

    if args.store_minio:
        print(f"Résultat batch stocké dans MinIO : {result['stored']['batch']}")
        for doc_key in result["stored"]["documents"]:
            print(f"Résultat document stocké dans MinIO : {doc_key}")
    else:
        print("Écriture MinIO désactivée.")


if __name__ == "__main__":
    main()