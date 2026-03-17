"""
nlp_ocr/pipeline.py
════════════════════
Orchestrateur principal. Point d'entrée unique : extract().

Usage::

    from nlp_ocr.pipeline import extract

    result = extract("ma_facture.pdf")
    print(result.classification.document_type)    # "facture"
    print(result.facture.montant_ttc.value)        # "9000.00"
    print(result.facture.montant_ttc.confidence)   # 0.87
    print(result.facture.montant_ttc.method)       # "regex_pattern"
    print(result.overall_confidence)               # 0.81
    print(result.extraction_warnings)              # []
"""
from __future__ import annotations
import logging, time, uuid
from pathlib import Path
from typing import Union

from nlp_ocr.preprocessor  import preprocess
from nlp_ocr.ocr_engine    import run_ocr
from nlp_ocr.classifier    import classify_document
from nlp_ocr.ner_extractor import extract_fields
from nlp_ocr.validator     import (validate_facture, validate_attestation_urssaf,
                                    validate_rib, validate_kbis)
from nlp_ocr.confidence    import apply_validation_adjustments, compute_audit
from nlp_ocr.schema        import ExtractionResult, OcrMetadata, DocumentType

log = logging.getLogger(__name__)

_VALIDATORS = {
    DocumentType.FACTURE:            validate_facture,
    DocumentType.ATTESTATION_URSSAF: validate_attestation_urssaf,
    DocumentType.RIB:                validate_rib,
    DocumentType.KBIS:               validate_kbis,
}


def extract(
    source: Union[str, Path, bytes],
    file_name:    str       = "document",
    document_id:  str|None = None,
    force_easyocr: bool    = False,
    estimated_dpi: int     = 72,
) -> ExtractionResult:
    """
    Extrait les champs structurés d'un document administratif français.

    Args:
        source        : chemin fichier (str/Path) ou bytes bruts (PDF ou image)
        file_name     : nom du fichier original (logs & stockage)
        document_id   : UUID auto-généré si absent
        force_easyocr : bypasse Tesseract
        estimated_dpi : aide à décider l'upscaling

    Returns:
        ExtractionResult — JSON-sérialisable via .model_dump_json()
    """
    t0     = time.perf_counter()
    doc_id = document_id or str(uuid.uuid4())
    log.info(f"[{doc_id}] ── Début extraction : {file_name}")

    # ── 1. Pré-traitement ─────────────────────────────────────────────────────
    prep = preprocess(source, estimated_dpi=estimated_dpi)

    # ── 2. OCR ────────────────────────────────────────────────────────────────
    ocr  = run_ocr(prep.images, force_easyocr=force_easyocr)
    meta = OcrMetadata(
        engine_primary      = ocr.engine_primary,
        engine_used         = ocr.engine_used,
        fallback_triggered  = ocr.fallback_triggered,
        ocr_confidence_avg  = ocr.mean_confidence,
        page_count          = len(prep.images),
        preprocessing_steps = prep.steps,
        processing_time_ms  = ocr.processing_time_ms,
        raw_text_length     = len(ocr.full_text),
    )

    # ── 3. Classification ─────────────────────────────────────────────────────
    clf  = classify_document(ocr.full_text)

    # ── 4. Extraction NER ─────────────────────────────────────────────────────
    data = extract_fields(ocr.full_text, clf.document_type)

    # ── 5. Assemblage ─────────────────────────────────────────────────────────
    result = ExtractionResult(document_id=doc_id, file_name=file_name,
                              classification=clf, ocr_metadata=meta,
                              raw_text=ocr.full_text)
    dt = clf.document_type
    if   dt == DocumentType.FACTURE            and data: result.facture            = data
    elif dt == DocumentType.DEVIS              and data: result.devis              = data
    elif dt == DocumentType.ATTESTATION_SIRET  and data: result.attestation_siret  = data
    elif dt == DocumentType.ATTESTATION_URSSAF and data: result.attestation_urssaf = data
    elif dt == DocumentType.KBIS               and data: result.kbis               = data
    elif dt == DocumentType.RIB                and data: result.rib                = data

    # ── 6. Validation métier ──────────────────────────────────────────────────
    vfn = _VALIDATORS.get(dt)
    if vfn and data:
        report = vfn(data)
        apply_validation_adjustments(result, report)
        result.extraction_warnings.extend(report.warnings + report.errors)

    # ── 7. Score de confiance global ──────────────────────────────────────────
    audit = compute_audit(result, ocr.mean_confidence)
    if audit.review_required:
        result.extraction_warnings.append(
            f"RÉVISION REQUISE : confiance={audit.overall:.2f}")

    log.info(f"[{doc_id}] ── {(time.perf_counter()-t0)*1000:.0f}ms | "
             f"type={dt.value} | conf={result.overall_confidence:.2f} | "
             f"champs={result.fields_extracted} | warns={len(result.extraction_warnings)}")
    return result


def extract_batch(
    sources: list[tuple[Union[str, Path, bytes], str]],
    **kwargs,
) -> list[ExtractionResult]:
    """
    Traite plusieurs documents en séquence.

    Args:
        sources : list de (source, file_name)
    """
    results = []
    for i, (src, name) in enumerate(sources, 1):
        log.info(f"Lot {i}/{len(sources)} : {name}")
        try:    results.append(extract(src, file_name=name, **kwargs))
        except Exception as e: log.error(f"Échec {name} : {e}", exc_info=True)
    return results
