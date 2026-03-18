"""
nlp_ocr/classifier.py
══════════════════════
Classification du type de document par scoring de mots-clés pondérés.

Usage::

    from nlp_ocr.classifier import classify_document
    r = classify_document(ocr_text)
    print(r.document_type)   # DocumentType.FACTURE
    print(r.confidence)      # 0.72
"""
from __future__ import annotations
import logging, re
from collections import defaultdict
from nlp_ocr.schema import ClassificationResult, DocumentType

log = logging.getLogger(__name__)

# (pattern, poids) — 4.0 = très discriminant, 0.8 = signal faible
SIGNATURES: dict[DocumentType, list[tuple[str, float]]] = {

    DocumentType.FACTURE: [
        (r"\bfacture\b",                         4.0),
        (r"\binvoice\b",                          2.0),
        (r"\bnum[eé]ro\s*(?:de\s*)?facture\b",   3.0),
        (r"\bmontant\s*(?:total\s*)?ttc\b",       2.5),
        (r"\bmontant\s*(?:total\s*)?ht\b",        2.0),
        (r"\btaux\s*(?:de\s*)?tva\b",             1.5),
        (r"\b[eé]ch[eé]ance\b",                   1.0),
    ],
    DocumentType.DEVIS: [
        (r"\bdevis\b",                             4.0),
        (r"\bproposition\s*commerciale\b",          3.0),
        (r"\bvalable\s*jusqu",                      2.5),
        (r"\bdate\s*(?:de\s*)?validit[eé]\b",       2.0),
        (r"\boffre\s*(?:de\s*prix)?\b",             1.5),
        (r"\bprestation\b",                         0.8),
    ],
    DocumentType.ATTESTATION_SIRET: [
        (r"\bavis\s*(?:de\s*)?situation\b",         4.0),
        (r"\binfogreffe\b",                          3.0),
        (r"\binsee\b",                               2.5),
        (r"\bcode?\s*(?:ape|naf)\b",                 2.5),
        (r"\b[eé]tablissement\b",                    1.0),
    ],
    DocumentType.ATTESTATION_URSSAF: [
        (r"\burssaf\b",                              5.0),
        (r"\battestation\s*(?:de\s*)?vigilance\b",   5.0),
        (r"\bcotisations?\s*sociales?\b",             2.5),
        (r"\bnet[- ]entreprises?\.fr\b",              2.0),
        (r"\bd[eé]clarations?\s*sociales?\b",         2.0),
    ],
    DocumentType.KBIS: [
        (r"\bkbis\b",                                5.0),
        (r"\bregistre\s*(?:du\s*)?commerce\b",        4.0),
        (r"\bgreffe\b",                               3.5),
        (r"\bimmatriculation\b",                      3.0),
        (r"\bforme\s*juridique\b",                    2.5),
        (r"\bcapital\s*social\b",                     2.5),
    ],
    DocumentType.RIB: [
        (r"\brib\b",                                  5.0),
        (r"\brelev[eé]\s*(?:d['']\s*)?identit[eé]\s*bancaire\b", 5.0),
        (r"\biban\b",                                  3.5),
        (r"\bbic\b",                                   2.5),
        (r"\bdomiciliation\b",                         2.5),
        (r"\bcode\s*(?:banque|guichet)\b",              2.5),
    ],
}


def _boosts(text: str) -> dict[DocumentType, float]:
    b: dict[DocumentType, float] = defaultdict(float)
    if re.search(r"\bFR\d{2}(?:[\s]?\d{4}){5}[\s]?\d{3}\b", text):
        b[DocumentType.RIB] += 2.5
    if re.search(r"\bRCS\s+[A-Z][a-z]+\b", text):
        b[DocumentType.KBIS] += 2.5
    if re.search(r"\b(?:FAC|INV|F)\s*[-/]?\s*\d{4,}", text, re.I):
        b[DocumentType.FACTURE] += 1.5
    if re.search(r"\bvalide\s+du\b.{1,60}\bau\b", text, re.I | re.S):
        b[DocumentType.ATTESTATION_URSSAF] += 2.0
    return dict(b)


def classify_document(text: str) -> ClassificationResult:
    """
    Classifie le type de document à partir du texte OCR.

    Returns:
        ClassificationResult(document_type, confidence, scores)
    """
    if not text.strip():
        return ClassificationResult(document_type=DocumentType.INCONNU, confidence=0.0,
                                    scores={t.value: 0.0 for t in DocumentType
                                            if t != DocumentType.INCONNU})
    tl = text.lower()
    raw: dict[str, float] = {}
    for dt, patterns in SIGNATURES.items():
        raw[dt.value] = sum(len(re.findall(p, tl)) * w for p, w in patterns)
    for dt, boost in _boosts(text).items():
        raw[dt.value] = raw.get(dt.value, 0.0) + boost

    total = sum(raw.values())
    norm  = {k: round(v / total, 4) for k, v in raw.items()} if total > 0 else {k: 0.0 for k in raw}

    if not norm or all(v == 0 for v in norm.values()):
        best_type, best_conf = DocumentType.INCONNU, 0.0
    else:
        best_key  = max(norm, key=norm.__getitem__)
        best_type = DocumentType(best_key)
        best_conf = norm[best_key]

    log.info(f"Classification → {best_type.value} (conf={best_conf:.2f})")
    return ClassificationResult(document_type=best_type, confidence=best_conf, scores=norm)
