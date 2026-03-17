"""
nlp_ocr/preprocessor.py
════════════════════════
Pré-traitement image avant OCR (OpenCV).

Étapes : PDF→PIL · grayscale · upscale · deskew · denoise · binarize · morph_cleanup
"""
from __future__ import annotations
import io, math, logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

import cv2
import numpy as np
from PIL import Image

log = logging.getLogger(__name__)

MIN_DPI, TARGET_DPI, MAX_SKEW = 150, 300, 45


def _pdf_to_pil(data: bytes) -> list[Image.Image]:
    try:
        import fitz
        doc = fitz.open(stream=data, filetype="pdf")
        pages = []
        for pg in doc:
            mat = fitz.Matrix(TARGET_DPI / 72, TARGET_DPI / 72)
            pix = pg.get_pixmap(matrix=mat, alpha=False)
            pages.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
        doc.close()
        return pages
    except ImportError:
        from pdf2image import convert_from_bytes
        return convert_from_bytes(data, dpi=TARGET_DPI)


def _gray(img: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img


def _upscale(img: np.ndarray, dpi: int) -> tuple[np.ndarray, list[str]]:
    if dpi >= MIN_DPI:
        return img, []
    s = TARGET_DPI / dpi
    h, w = img.shape[:2]
    return cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_CUBIC), [f"upscale_x{s:.1f}"]


def _skew_angle(img: np.ndarray) -> float:
    edges = cv2.Canny(img, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, threshold=100)
    if lines is None:
        return 0.0
    angles = [math.degrees(l[0][1]) - 90 for l in lines if abs(math.degrees(l[0][1]) - 90) < MAX_SKEW]
    if not angles:
        return 0.0
    med = float(np.median(angles))
    return med if abs(med) > 0.5 else 0.0


def _deskew(img: np.ndarray) -> tuple[np.ndarray, float]:
    a = _skew_angle(img)
    if a == 0.0:
        return img, 0.0
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), a, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC,
                          borderMode=cv2.BORDER_REPLICATE), a


def _denoise(img: np.ndarray) -> np.ndarray:
    return cv2.fastNlMeansDenoising(img, h=10, templateWindowSize=7, searchWindowSize=21)


def _binarize(img: np.ndarray) -> np.ndarray:
    _, otsu = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    adapt   = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
                                    cv2.THRESH_BINARY, 31, 10)
    chosen  = otsu if np.sum(otsu == 255) >= np.sum(adapt == 255) else adapt
    kernel  = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
    return cv2.morphologyEx(chosen, cv2.MORPH_OPEN, kernel)


@dataclass
class PreprocessingResult:
    images:      list[np.ndarray]
    steps:       list[str]
    skew_angles: list[float] = field(default_factory=list)


def preprocess(
    source: Union[str, Path, bytes],
    is_pdf: bool | None = None,
    estimated_dpi: int = 72,
    apply_deskew:   bool = True,
    apply_denoise:  bool = True,
    apply_binarize: bool = True,
) -> PreprocessingResult:
    """
    Pré-traite un document (PDF ou image) pour l'OCR.

    Usage::

        from nlp_ocr.preprocessor import preprocess
        result = preprocess("scan.pdf")
        # result.images  → liste de np.ndarray (une par page)
        # result.steps   → ['grayscale', 'deskew_2.1deg', 'denoise', 'binarize']
    """
    if isinstance(source, (str, Path)):
        p = Path(source)
        data = p.read_bytes()
        is_pdf = is_pdf if is_pdf is not None else p.suffix.lower() == ".pdf"
    else:
        data   = source
        is_pdf = is_pdf if is_pdf is not None else data[:4] == b"%PDF"

    pil_imgs = _pdf_to_pil(data) if is_pdf else [Image.open(io.BytesIO(data)).convert("RGB")]
    steps: list[str] = ["pdf_to_image"] if is_pdf else []
    angles: list[float] = []
    processed: list[np.ndarray] = []

    for pil in pil_imgs:
        arr = np.array(pil)
        if arr.ndim == 3 and arr.shape[2] == 3:
            arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)

        g = _gray(arr);                    steps.append("grayscale")
        g, up = _upscale(g, estimated_dpi); steps.extend(up)

        angle = 0.0
        if apply_deskew:
            g, angle = _deskew(g)
            if angle != 0.0: steps.append(f"deskew_{angle:.1f}deg")
        angles.append(angle)

        if apply_denoise:
            g = _denoise(g); steps.append("denoise")
        if apply_binarize:
            g = _binarize(g); steps.append("binarize")

        processed.append(g)

    unique = list(dict.fromkeys(steps))
    log.info(f"Preprocessing: {len(processed)} page(s), steps={unique}")
    return PreprocessingResult(images=processed, steps=unique, skew_angles=angles)
