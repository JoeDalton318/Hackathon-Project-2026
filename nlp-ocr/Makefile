.PHONY: install test test-unit test-int dataset api docker-build docker-up docker-down clean help

PYTHON  := python
PYTEST  := pytest -v
DATASET := ./dataset
COUNT   := 60

## Installe les dépendances Python + modèle spaCy
install:
	pip install -r requirements.txt
	pip install -e .
	python -m spacy download fr_core_news_md
	@echo "✓ Installation terminée"
	@echo "  → sudo apt install tesseract-ocr tesseract-ocr-fra"

## Lance tous les tests
test:
	$(PYTEST) tests/

## Tests unitaires rapides (sans OCR/Tesseract)
test-unit:
	$(PYTEST) tests/test_validator.py tests/test_classifier.py tests/test_ner_extractor.py

## Tests d'intégration (nécessite Tesseract + fpdf2)
test-int:
	$(PYTEST) tests/test_pipeline.py -v

## Génère le dataset synthétique
dataset:
	$(PYTHON) scripts/generate_dataset.py --output $(DATASET) --count $(COUNT) --seed 42
	@echo "✓ Dataset → $(DATASET)/"

## Lance l'API FastAPI en mode dev
api:
	uvicorn api.app:app --reload --host 0.0.0.0 --port 8000

## Build l'image Docker
docker-build:
	docker build -t ocr-extraction:latest .

## Lance la stack complète (API + MinIO + MongoDB)
docker-up:
	docker compose up -d
	@echo "  API      → http://localhost:8000/docs"
	@echo "  MinIO UI → http://localhost:9001  (minioadmin / minioadmin123)"

## Arrête la stack
docker-down:
	docker compose down

## Nettoie les fichiers temporaires
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	rm -rf .pytest_cache dist build *.egg-info

## Affiche cette aide
help:
	@grep -E '^##' $(MAKEFILE_LIST) | sed 's/## //'
