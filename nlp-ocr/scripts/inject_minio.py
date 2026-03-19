"""
scripts/inject_minio.py
════════════════════════
Injecte des documents dans la zone RAW de MinIO sans les supprimer.
Permet à l'équipe validation de tester directement depuis MinIO.

Usage :
    python scripts/inject_minio.py --source ./dataset/pdfs --env .env
"""

import argparse
import json
import logging
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("inject-minio")


# ─── Chargement du .env ───────────────────────────────────────────────────────

def _load_env(env_path: str):
    """Charge les variables du fichier .env dans os.environ."""
    p = Path(env_path)
    if not p.exists():
        log.warning(f".env non trouvé à {env_path}, utilise les variables système")
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())
    log.info(f"Variables chargées depuis {env_path}")


# ─── Client MinIO ─────────────────────────────────────────────────────────────

def _get_minio_client():
    try:
        from minio import Minio
    except ImportError:
        log.error("Package 'minio' absent. Lance : pip install minio")
        sys.exit(1)

    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    access   = os.environ.get("MINIO_ACCESS_KEY", "")
    secret   = os.environ.get("MINIO_SECRET_KEY", "")
    secure   = os.environ.get("MINIO_SECURE", "false").lower() == "true"

    if not access or not secret:
        log.error("MINIO_ACCESS_KEY ou MINIO_SECRET_KEY manquant dans .env")
        sys.exit(1)

    client = Minio(endpoint, access_key=access, secret_key=secret, secure=secure)
    log.info(f"Connecté à MinIO : {endpoint}")
    return client


# ─── Création du bucket si absent ────────────────────────────────────────────

def _ensure_bucket(client, bucket: str):
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        log.info(f"Bucket '{bucket}' créé")
    else:
        log.info(f"Bucket '{bucket}' déjà existant")


# ─── Injection d'un fichier ───────────────────────────────────────────────────

def _inject_file(
    client,
    bucket:    str,
    file_path: Path,
    doc_id:    str,
) -> dict:
    """
    Envoie un fichier dans la zone RAW de MinIO.
    Ne supprime JAMAIS le fichier source ni l'objet MinIO existant.
    Retourne les métadonnées de l'objet créé.
    """
    ext = file_path.suffix.lstrip(".") or "bin"
    ct  = "application/pdf" if ext == "pdf" else "image/jpeg"

    today = datetime.utcnow()
    key   = (
        f"raw/{today.year}/{today.month:02d}/{today.day:02d}"
        f"/{doc_id}/{file_path.name}"
    )

    file_bytes = file_path.read_bytes()

    client.put_object(
        bucket_name  = bucket,
        object_name  = key,
        data         = __import__("io").BytesIO(file_bytes),
        length       = len(file_bytes),
        content_type = ct,
        metadata     = {
            "document-id":       doc_id,
            "original-filename": file_path.name,
            "injected-at":       datetime.utcnow().isoformat(),
            "source":            "inject_minio.py",
        },
    )

    log.info(f"  ✓ {file_path.name} → {key}")
    return {
        "document_id":    doc_id,
        "file_name":      file_path.name,
        "minio_key":      key,
        "bucket":         bucket,
        "size_bytes":     len(file_bytes),
        "injected_at":    datetime.utcnow().isoformat(),
    }


# ─── Point d'entrée ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Injecte des fichiers dans MinIO zone RAW (sans suppression)"
    )
    parser.add_argument(
        "--source",
        default="./dataset/pdfs",
        help="Dossier contenant les fichiers à injecter (défaut: ./dataset/pdfs)",
    )
    parser.add_argument(
        "--bucket",
        default="datalake",
        help="Nom du bucket MinIO (défaut: datalake)",
    )
    parser.add_argument(
        "--env",
        default=".env",
        help="Chemin vers le fichier .env (défaut: .env)",
    )
    parser.add_argument(
        "--pattern",
        default="*.pdf",
        help="Pattern des fichiers à injecter (défaut: *.pdf)",
    )
    parser.add_argument(
        "--output",
        default="./dataset/minio_manifest.json",
        help="Fichier JSON de sortie avec les clés MinIO (pour l'équipe validation)",
    )
    args = parser.parse_args()

    # Charge .env
    _load_env(args.env)

    # Connexion MinIO
    client = _get_minio_client()
    _ensure_bucket(client, args.bucket)

    # Trouve les fichiers
    source_dir = Path(args.source)
    if not source_dir.exists():
        log.error(f"Dossier source introuvable : {source_dir}")
        sys.exit(1)

    files = sorted(source_dir.glob(args.pattern))
    if not files:
        log.warning(f"Aucun fichier trouvé avec le pattern '{args.pattern}' dans {source_dir}")
        sys.exit(0)

    log.info(f"{len(files)} fichier(s) trouvé(s) dans {source_dir}")

    # Injection
    manifest = []
    errors   = []

    for file_path in files:
        doc_id = str(uuid.uuid4())
        try:
            meta = _inject_file(client, args.bucket, file_path, doc_id)
            manifest.append(meta)
        except Exception as e:
            log.error(f"  ✗ {file_path.name} : {e}")
            errors.append({"file": str(file_path), "error": str(e)})

    # Sauvegarde le manifest pour l'équipe validation
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Résumé
    log.info("")
    log.info(f"Injection terminée :")
    log.info(f"  ✓ {len(manifest)} fichier(s) injectés")
    log.info(f"  ✗ {len(errors)} erreur(s)")
    log.info(f"  Manifest sauvegardé → {output_path}")
    log.info("")
    log.info("Ta collègue peut maintenant accéder aux fichiers depuis MinIO :")
    log.info(f"  Bucket : {args.bucket}")
    log.info(f"  Préfixe : raw/YYYY/MM/DD/<doc_id>/")


if __name__ == "__main__":
    main()