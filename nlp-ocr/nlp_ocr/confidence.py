"""
nlp_ocr/confidence.py
══════════════════════
Score de confiance global et ajustement post-validation.

Score global = 20% OCR · 60% champs · 20% classification
"""
from __future__ import annotations
import logging
from dataclasses import dataclass
from typing import Any

from nlp_ocr.schema import ExtractedField
from nlp_ocr.validator import ValidationReport, FieldValidation

log = logging.getLogger(__name__)

RELIABLE_THRESHOLD = 0.75
REVIEW_THRESHOLD   = 0.70
CRITICAL_FIELDS    = {"siret", "iban", "montant_ttc", "date_expiration"}


@dataclass
class ConfidenceAudit:
    field_scores:      dict[str, float]
    overall:           float
    reliable_fields:   list[str]
    unreliable_fields: list[str]
    review_required:   bool

    def summary(self) -> str:
        return (f"overall={self.overall:.2f} fiables={len(self.reliable_fields)} "
                f"incertains={len(self.unreliable_fields)} "
                f"révision={'OUI' if self.review_required else 'NON'}")


def _collect(obj: Any, prefix: str = "") -> list[tuple[str, ExtractedField]]:
    if obj is None: return []
    if isinstance(obj, ExtractedField): return [(prefix, obj)]
    if hasattr(obj, "model_fields"):
        res = []
        for fname in obj.model_fields:
            val = getattr(obj, fname, None)
            res.extend(_collect(val, f"{prefix}.{fname}" if prefix else fname))
        return res
    return []


def apply_validation_adjustments(extraction_result, report: ValidationReport) -> None:
    """Ajuste en place les confidences des champs selon le rapport de validation."""
    check_map  = {c.field_name: c for c in report.checks}
    typed_data = extraction_result.get_typed_data()
    if not typed_data: return

    for path, ef in _collect(typed_data):
        check = check_map.get(path.split(".")[-1])
        if not check or ef.value is None: continue
        new_conf = ef.confidence
        if check.is_valid:
            new_conf = min(1.0, new_conf + check.confidence_boost)
        else:
            new_conf = max(0.0, new_conf - check.confidence_penalty)
        adjusted = ExtractedField(value=ef.value, confidence=round(new_conf, 4),
                                  method=ef.method, raw_ocr=ef.raw_ocr)
        parts  = path.split(".")
        parent = typed_data
        for part in parts[:-1]:
            parent = getattr(parent, part, None)
            if parent is None: break
        if parent:
            try: setattr(parent, parts[-1], adjusted)
            except Exception: pass


def compute_audit(extraction_result, ocr_confidence: float) -> ConfidenceAudit:
    """
    Calcule le score de confiance global et l'audit de qualité.
    Écrit overall_confidence, fields_extracted, fields_reliable dans extraction_result.
    """
    typed_data   = extraction_result.get_typed_data()
    all_fields   = _collect(typed_data) if typed_data else []
    field_scores = {p: ef.confidence for p, ef in all_fields if ef.value is not None}

    field_avg  = sum(field_scores.values()) / len(field_scores) if field_scores else 0.0
    class_conf = extraction_result.classification.confidence
    overall    = round(0.20 * ocr_confidence + 0.60 * field_avg + 0.20 * class_conf, 4)

    reliable   = [p for p, s in field_scores.items() if s >= RELIABLE_THRESHOLD]
    unreliable = [p for p, s in field_scores.items() if s < RELIABLE_THRESHOLD]
    critical   = any(p.split(".")[-1] in CRITICAL_FIELDS for p in unreliable)
    review     = overall < REVIEW_THRESHOLD or critical

    audit = ConfidenceAudit(field_scores=field_scores, overall=overall,
                            reliable_fields=reliable, unreliable_fields=unreliable,
                            review_required=review)
    log.info(f"Audit confiance : {audit.summary()}")

    extraction_result.overall_confidence = overall
    extraction_result.fields_extracted   = len(field_scores)
    extraction_result.fields_reliable    = len(reliable)
    return audit
