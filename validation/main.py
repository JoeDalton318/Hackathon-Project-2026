import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from app.anomaly_model import DocumentAnomalyModel
from app.insee_client import InseeClient
from app.models import BatchInput
from app.validation_engine import AnomalyEngine


BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")

DOC_TYPE_MAP = {
    "facture": "FACTURE",
    "devis": "DEVIS",
    "extrait_kbis": "KBIS",
    "kbis": "KBIS",
    "rib": "RIB",
    "attestation_siret": "ATTESTATION_SIRET",
    "attestation_vigilance_urssaf": "ATTESTATION_URSSAF",
    "attestation_urssaf": "ATTESTATION_URSSAF",
    "attestation": "UNKNOWN",
    "unknown": "UNKNOWN",
}


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, payload: Dict[str, Any]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def normalize_doc_type(value: Optional[str]) -> str:
    if not value:
        return "unknown"
    return str(value).strip().lower()


def to_backend_doc_type(value: str) -> str:
    return DOC_TYPE_MAP.get(normalize_doc_type(value), "unknown")


def build_batch_input(payload: Dict[str, Any]) -> BatchInput:

    if "documents" in payload and isinstance(payload["documents"], list):
        batch_id = payload.get("batch_id") or f"batch_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        documents = []

        for doc in payload["documents"]:
            documents.append({
                "document_id": doc.get("document_id"),
                "doc_type": normalize_doc_type(doc.get("doc_type") or doc.get("document_type")),
                "fields": doc.get("fields") or doc.get("extracted_data") or {},
                "metadata": doc.get("metadata") or {},
            })

        return BatchInput(batch_id=batch_id, documents=documents)

    if "document_id" in payload:
        return BatchInput(
            batch_id=payload.get("batch_id") or f"batch_{payload['document_id']}",
            documents=[{
                "document_id": payload["document_id"],
                "doc_type": normalize_doc_type(payload.get("doc_type") or payload.get("document_type")),
                "fields": payload.get("fields") or payload.get("extracted_data") or {},
                "metadata": payload.get("metadata") or {},
            }],
        )

    raise ValueError("Format JSON non supporté.")


def load_ml_model(model_path: str = "curated/anomaly_model.joblib") -> Optional[DocumentAnomalyModel]:
    path = Path(model_path)
    if path.exists():
        return DocumentAnomalyModel.load(str(path))
    return None


def build_document_anomalies(document_id: str, validation_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    anomalies = []

    for alert in validation_result.get("alerts", []):
        if document_id in alert.get("documents", []):
            anomalies.append({
                "type": alert.get("rule_code"),
                "severity": str(alert.get("severity", "")).upper(),
                "description": alert.get("message"),
                "document_ids": alert.get("documents", []),
                "details": alert.get("details", {}),
            })

    return anomalies


def send_callback_to_backend(batch: BatchInput, validation_result: Dict[str, Any]) -> None:
    if not INTERNAL_API_SECRET:
        raise ValueError("INTERNAL_API_SECRET manquant.")

    for doc in batch.documents:
        payload = {
            "document_id": doc.document_id,
            "status": "DONE",
            "document_type": to_backend_doc_type(doc.doc_type),
            "extracted_data": doc.fields.model_dump(),
            "anomalies": build_document_anomalies(doc.document_id, validation_result),
            "error_message": None,
        }

        response = requests.post(
            f"{BACKEND_URL}/api/internal/pipeline/result",
            json=payload,
            headers={"X-Internal-Secret": INTERNAL_API_SECRET},
            timeout=10,
        )
        response.raise_for_status()


def run(input_path: str, output_path: str, send_backend: bool = False) -> Dict[str, Any]:
    payload = load_json(input_path)
    batch = build_batch_input(payload)

    anomaly_model = load_ml_model()

    engine = AnomalyEngine(
        insee_client=InseeClient(enabled=True, fallback_to_mock=True),
        anomaly_model=anomaly_model,
        reference_date=datetime.utcnow(),
        engine_version="1.1.0",
    )

    result = engine.run(batch)
    result_dict = result.model_dump()

    save_json(output_path, result_dict)

    if send_backend:
        send_callback_to_backend(batch, result_dict)

    return result_dict


def default_output_path(input_path: str) -> str:
    p = Path(input_path)
    return str(p.parent / f"{p.stem}_validation_result.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Chemin du JSON d'entrée")
    parser.add_argument("--output", help="Chemin du JSON de sortie")
    parser.add_argument("--send-backend", action="store_true", help="Envoie le callback au backend")
    args = parser.parse_args()

    output_path = args.output or default_output_path(args.input)

    result = run(
        input_path=args.input,
        output_path=output_path,
        send_backend=args.send_backend,
    )

    print(json.dumps({
        "status": "ok",
        "batch_id": result["batch_id"],
        "decision": result["decision"],
        "global_score": result["global_score"],
        "output_path": output_path,
    }, ensure_ascii=False, indent=2))