"""
nlp_ocr/ocr_engine.py
══════════════════════
Tesseract (primaire) + EasyOCR (fallback si conf < seuil).

Usage::

    from nlp_ocr.ocr_engine import run_ocr
    result = run_ocr(images)          # images : list[np.ndarray]
    print(result.full_text)
    print(result.engine_used)         # "tesseract" | "easyocr"
    print(result.mean_confidence)     # 0.0 – 1.0
"""
from __future__ import annotations
import logging, re, time
from dataclasses import dataclass, field

import numpy as np
import pytesseract
from PIL import Image

log = logging.getLogger(__name__)

TESS_CONFIG        = "--oem 3 --psm 6 -l fra"
FALLBACK_THRESHOLD = 0.65
MIN_WORD_CONF      = 20

_easy = None

def _easyocr():
    global _easy
    if _easy is None:
        import easyocr
        log.info("Chargement EasyOCR (~3 s)…")
        _easy = easyocr.Reader(["fr", "en"], gpu=False, verbose=False)
    return _easy


@dataclass
class PageOcrResult:
    text:             str
    engine:           str
    mean_confidence:  float
    word_confidences: list[float] = field(default_factory=list)
    fallback:         bool        = False


@dataclass
class OcrResult:
    full_text:          str
    pages:              list[PageOcrResult]
    mean_confidence:    float
    engine_primary:     str   = "tesseract"
    engine_used:        str   = "tesseract"
    fallback_triggered: bool  = False
    processing_time_ms: float = 0.0


def _clean(text: str) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _tesseract(img: np.ndarray) -> PageOcrResult:
    pil  = Image.fromarray(img)
    data = pytesseract.image_to_data(pil, config=TESS_CONFIG,
                                     output_type=pytesseract.Output.DICT)
    confs = []
    for c, w in zip(data["conf"], data["text"]):
        try: cv = int(c)
        except (ValueError, TypeError): continue
        if cv >= MIN_WORD_CONF and str(w).strip():
            confs.append(cv / 100.0)
    text = pytesseract.image_to_string(pil, config=TESS_CONFIG).strip()
    return PageOcrResult(text=text, engine="tesseract",
                         mean_confidence=float(np.mean(confs)) if confs else 0.0,
                         word_confidences=confs)


def _easyocr_run(img: np.ndarray) -> PageOcrResult:
    results = _easyocr().readtext(img, detail=1, paragraph=False)
    if not results:
        return PageOcrResult(text="", engine="easyocr", mean_confidence=0.0)
    results.sort(key=lambda r: (r[0][0][1], r[0][0][0]))
    lines, confs = [], []
    for (_, txt, conf) in results:
        if txt.strip():
            lines.append(txt.strip()); confs.append(float(conf))
    return PageOcrResult(text=" ".join(lines), engine="easyocr",
                         mean_confidence=float(np.mean(confs)) if confs else 0.0,
                         word_confidences=confs)


def run_ocr(
    images: list[np.ndarray],
    force_easyocr: bool = False,
    fallback_threshold: float = FALLBACK_THRESHOLD,
) -> OcrResult:
    """
    Lance l'OCR sur une liste d'images pré-traitées.

    Args:
        images             : list[np.ndarray] — une image par page
        force_easyocr      : bypasse Tesseract
        fallback_threshold : seuil Tesseract sous lequel EasyOCR est déclenché

    Returns:
        OcrResult avec full_text, mean_confidence, engine_used
    """
    t0 = time.perf_counter()
    pages: list[PageOcrResult] = []
    any_fallback = False
    engine_used  = "easyocr" if force_easyocr else "tesseract"

    for i, img in enumerate(images):
        log.debug(f"OCR page {i+1}/{len(images)}")
        if force_easyocr:
            p = _easyocr_run(img); p.fallback = True
        else:
            p = _tesseract(img)
            log.debug(f"  Tesseract conf={p.mean_confidence:.2f}")
            if p.mean_confidence < fallback_threshold:
                log.info(f"  Page {i+1}: fallback EasyOCR (conf={p.mean_confidence:.2f})")
                e = _easyocr_run(img); e.fallback = True
                if e.mean_confidence > p.mean_confidence:
                    p = e; engine_used = "easyocr"; any_fallback = True
        p.text = _clean(p.text)
        pages.append(p)

    full_text  = "\n\n".join(p.text for p in pages if p.text)
    all_confs  = [c for p in pages for c in p.word_confidences]
    mean_conf  = float(np.mean(all_confs)) if all_confs else 0.0
    elapsed    = (time.perf_counter() - t0) * 1000

    log.info(f"OCR: engine={engine_used} conf={mean_conf:.2f} t={elapsed:.0f}ms")
    return OcrResult(full_text=full_text, pages=pages, mean_confidence=mean_conf,
                     engine_primary="easyocr" if force_easyocr else "tesseract",
                     engine_used=engine_used, fallback_triggered=any_fallback,
                     processing_time_ms=elapsed)
