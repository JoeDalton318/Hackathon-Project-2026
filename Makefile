# ─── Backend ──────────────────────────────────────────────────────────────────

.PHONY: fastapi-dev

# Demarrer fastapi en mode dev
fastapi-dev:
	fastapi dev backend/app/main.py --reload


# ─── NLP-OCR — Juba ──────────────────────────────────────────────────────────

.PHONY: ocr-install ocr-test ocr-test-unit ocr-dataset ocr-docker-build

# Installer les dépendances OCR + modèle spaCy
ocr-install:
	cd nlp-ocr && pip install -r requirements.txt && pip install -e . && python -m spacy download fr_core_news_md

# Lancer tous les tests OCR
ocr-test:
	cd nlp-ocr && pytest tests/ -v

# Tests unitaires rapides (sans Tesseract)
ocr-test-unit:
	cd nlp-ocr && pytest tests/test_validator.py tests/test_classifier.py tests/test_ner_extractor.py -v

# Générer le dataset synthétique
ocr-dataset:
	cd nlp-ocr && python scripts/generate_dataset.py --output ./dataset --count 60 --seed 42

# Build l'image Docker OCR
ocr-docker-build:
	cd nlp-ocr && docker build -t ocr-extraction:latest .

# Injecter les fichiers dans MinIO zone RAW (sans suppression)
ocr-inject:
	cd nlp-ocr && python scripts/inject_minio.py --source ./dataset/pdfs --env .env