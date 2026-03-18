import os
from pathlib import Path
import pytesseract

from nlp_ocr.pipeline import extract
from storage.datalake import store_all_zones

if os.getenv("TESSERACT_CMD"):
    pytesseract.pytesseract.tesseract_cmd = os.getenv("TESSERACT_CMD")

pdf_dir = Path("dataset/pdfs")
files = sorted(pdf_dir.glob("*.pdf"))

if not files:
    raise SystemExit("Aucun fichier PDF trouvé dans dataset/pdfs")

for doc_path in files:
    print(f"\n=== Traitement {doc_path.name} ===")
    file_bytes = doc_path.read_bytes()

    result = extract(
        source=file_bytes,
        file_name=doc_path.name,
        estimated_dpi=300
    )

    stored = store_all_zones(file_bytes, doc_path.name, result)

    print("document_id:", result.document_id)
    print("type:", result.classification.document_type.value)
    print("ocr_engine:", result.ocr_metadata.engine_used)
    print("overall_confidence:", result.overall_confidence)
    print("stored:", stored)