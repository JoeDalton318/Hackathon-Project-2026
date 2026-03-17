# nlp-ocr — Pipeline OCR/NER · Hackathon 2026

**Rôle** : Juba — Lead NLP & OCR | **Branche** : `feature/juba-ocr`

---

## Installation

```bash
# 1. Dépendances système (Ubuntu/Debian)
sudo apt install tesseract-ocr tesseract-ocr-fra poppler-utils

# 2. Package Python
pip install -r requirements.txt
pip install -e .
python -m spacy download fr_core_news_md
```

---

## Usage

```python
from nlp_ocr import extract

result = extract("ma_facture.pdf")

print(result.classification.document_type)    # "facture"
print(result.facture.montant_ttc.value)        # "9000.00"
print(result.facture.montant_ttc.confidence)   # 0.87
print(result.facture.montant_ttc.method)       # "regex_pattern"
print(result.facture.emetteur.siret.value)     # "83245678901230"
print(result.overall_confidence)               # 0.81
print(result.extraction_warnings)              # []
```

---

## Commandes

```bash
make install       # dépendances + spaCy
make dataset       # génère 60 sets de documents synthétiques
make test-unit     # tests rapides (sans Tesseract)
make test          # tous les tests
make api           # uvicorn → http://localhost:8000/docs
make docker-up     # API + MinIO + MongoDB
```

---

## Structure

```
nlp_ocr/
├── schema.py        Modèles Pydantic (ExtractedField, ExtractionResult…)
├── preprocessor.py  OpenCV : deskew · denoise · binarize · upscale
├── ocr_engine.py    Tesseract primaire + EasyOCR fallback (seuil conf < 0.65)
├── classifier.py    Scoring mots-clés → 6 types de documents
├── ner_extractor.py Regex déterministes + spaCy NER fr_core_news_md
├── validator.py     Luhn SIRET/SIREN · ISO 13616 IBAN · TVA · dates · montants
├── confidence.py    Score global 20/60/20 (OCR·champs·classification)
└── pipeline.py      extract() — orchestrateur unique

scripts/
└── generate_dataset.py   Faker + fpdf2 : factures, URSSAF, RIBs + dégradations

api/app.py           FastAPI : POST /extract, POST /extract/batch, GET /documents
storage/datalake.py  MinIO 3 zones : raw · clean · curated
tests/               40+ assertions : validator, classifier, ner_extractor, pipeline
```

---

## Principe : zéro boîte noire

Chaque champ extrait expose sa traçabilité complète :

```json
{
  "value":      "83245678901230",
  "confidence": 0.92,
  "method":     "regex_pattern",
  "raw_ocr":    "SIRET : 83245678901230"
}
```

Types de méthodes : `regex_pattern` · `ner_model` · `rule_based` · `not_found`
