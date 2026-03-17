"""
api/app.py
═══════════
API REST FastAPI — Lead NLP & OCR

Démarrage::

    uvicorn api.app:app --reload --port 8000
    # Swagger → http://localhost:8000/docs
"""
from __future__ import annotations
import logging, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from nlp_ocr import extract, extract_batch, ExtractionResult
from storage.datalake import store_all_zones, list_curated

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s  %(levelname)-8s  %(message)s",
                    datefmt="%H:%M:%S")
log = logging.getLogger("ocr-api")

app = FastAPI(
    title="OCR Extraction API",
    description=(
        "Extraction structurée depuis des documents administratifs français.\n\n"
        "Chaque champ expose : **value**, **confidence** (0–1), **method**, **raw_ocr**."
    ),
    version="1.0.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health():
    return {"status": "ok", "service": "nlp-ocr", "version": "1.0.0"}


@app.post("/extract", response_model=ExtractionResult)
async def extract_doc(file: UploadFile = File(...)):
    """
    Upload un PDF ou une image → ExtractionResult JSON.

    Retourne le type détecté, tous les champs extraits avec leur confidence
    et méthode, ainsi que les avertissements de validation métier.
    """
    if not file.filename:
        raise HTTPException(400, "Aucun fichier fourni")
    content = await file.read()
    if not content:
        raise HTTPException(400, "Fichier vide")
    try:
        result = extract(source=content, file_name=file.filename)
        try:
            keys = store_all_zones(content, file.filename, result)
            log.info(f"Data Lake : {keys}")
        except Exception as e:
            log.warning(f"Stockage Data Lake non-fatal : {e}")
        return result
    except Exception as e:
        log.exception(f"Échec extraction {file.filename}")
        raise HTTPException(500, str(e))


@app.post("/extract/batch")
async def extract_batch_docs(files: list[UploadFile] = File(...)):
    """Upload multiple documents et extrait chacun en séquence."""
    if not files:
        raise HTTPException(400, "Aucun fichier fourni")
    sources, raws = [], {}
    for f in files:
        c = await f.read()
        if c:
            fname = f.filename or "inconnu"
            sources.append((c, fname)); raws[fname] = c
    results = extract_batch(sources)
    for r in results:
        if raw := raws.get(r.file_name):
            try: store_all_zones(raw, r.file_name, r)
            except Exception as e: log.warning(f"Stockage {r.file_name} : {e}")
    return {"count": len(results), "results": [r.model_dump() for r in results]}


@app.get("/documents")
def list_docs(
    doc_type: str = Query(default=None, description="Filtrer par type (facture, rib…)"),
    limit:    int = Query(default=50, le=200),
):
    """Liste les documents stockés dans la zone curée du Data Lake."""
    docs = list_curated(doc_type=doc_type, limit=limit)
    return {"count": len(docs), "documents": docs}


@app.get("/")
def root():
    return {"service": "OCR Extraction Pipeline — Juba",
            "endpoints": {"extract": "POST /extract", "batch": "POST /extract/batch",
                          "documents": "GET /documents", "swagger": "GET /docs"}}
