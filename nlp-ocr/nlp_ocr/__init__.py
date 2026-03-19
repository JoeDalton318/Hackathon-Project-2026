"""
nlp_ocr — Pipeline OCR/NER pour documents administratifs français.

Usage minimal::

    from nlp_ocr import extract

    result = extract("facture.pdf")
    print(result.classification.document_type)   # DocumentType.FACTURE
    print(result.facture.montant_ttc.value)       # "9000.00"
    print(result.overall_confidence)              # 0.81

Installation::

    pip install -e .
    python -m spacy download fr_core_news_md
    # + sudo apt install tesseract-ocr tesseract-ocr-fra
"""
from nlp_ocr.pipeline import extract, extract_batch
from nlp_ocr.schema   import (
    ExtractionResult, DocumentType, ExtractionMethod, ExtractedField,
)

__all__ = [
    "extract", "extract_batch",
    "ExtractionResult", "DocumentType", "ExtractionMethod", "ExtractedField",
]
__version__ = "1.0.0"