from __future__ import annotations

from typing import Any, Dict, List

from .models import BatchInput, ValidationResult


def build_document_validation_results(
    result: ValidationResult,
    batch: BatchInput,
) -> List[Dict[str, Any]]:
    alerts_by_doc: Dict[str, list] = {}
    signals_by_doc: Dict[str, list] = {}

    for alert in result.alerts:
        for doc_id in alert.documents:
            alerts_by_doc.setdefault(doc_id, []).append(alert.model_dump())

    for signal in result.signals:
        if signal.document_id:
            signals_by_doc.setdefault(signal.document_id, []).append(signal.model_dump())

    documents_by_id = {doc.document_id: doc for doc in batch.documents}
    document_ids = sorted(documents_by_id.keys())

    outputs: List[Dict[str, Any]] = []
    for document_id in document_ids:
        doc = documents_by_id[document_id]
        doc_alerts = alerts_by_doc.get(document_id, [])
        doc_signals = signals_by_doc.get(document_id, [])

        has_high_or_critical = any(a["severity"] in {"high", "critical"} for a in doc_alerts)
        has_medium = any(a["severity"] == "medium" for a in doc_alerts)

        if has_high_or_critical:
            decision = "blocked"
        elif has_medium:
            decision = "review"
        else:
            decision = "approved"

        suspected_document_type = None
        for alert in doc_alerts:
            if alert["rule_code"] == "DOCUMENT_TYPE_SUSPECT":
                suspected_document_type = alert["details"].get("suspected_type")
                break

        outputs.append({
            "document_id": document_id,
            "batch_id": result.batch_id,
            "validated_at": result.validated_at,
            "engine_version": result.engine_version,
            "document_type": doc.doc_type,
            "predicted_document_type": doc.doc_type,
            "suspected_document_type": suspected_document_type,
            "decision": decision,
            "alerts": doc_alerts,
            "signals": doc_signals,
            "summary": {
                "critical": sum(a["severity"] == "critical" for a in doc_alerts),
                "high": sum(a["severity"] == "high" for a in doc_alerts),
                "medium": sum(a["severity"] == "medium" for a in doc_alerts),
                "low": sum(a["severity"] == "low" for a in doc_alerts),
            },
            "extracted_data": doc.fields.model_dump(),
            "source": {
                "source_system": "validation",
                "ocr_source": doc.metadata.get("source"),
                "file_name": doc.metadata.get("file_name"),
                "classification": doc.metadata.get("classification"),
                "ocr_metadata": doc.metadata.get("ocr_metadata"),
                "extraction_warnings": doc.metadata.get("extraction_warnings", []),
                "source_extraction_key": doc.metadata.get("source_extraction_key"),
            },
        })

    return outputs