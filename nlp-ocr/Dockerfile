FROM python:3.11-slim

# ── Dépendances système ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-fra \
    libtesseract-dev \
    libglib2.0-0 \
    libgl1 \
    libsm6 \
    libxrender1 \
    libxext6 \
    poppler-utils \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ── Dépendances Python ────────────────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Modèle spaCy français ─────────────────────────────────────────────────────
RUN python -m spacy download fr_core_news_md

# ── Code ─────────────────────────────────────────────────────────────────────
COPY . .
RUN pip install --no-cache-dir -e .

# ✅ APRÈS — aucun credential en clair
ENV PYTHONUNBUFFERED=1 \
    LOG_LEVEL=INFO \
    MINIO_ENDPOINT="" \
    MINIO_ACCESS_KEY="" \
    MINIO_SECRET_KEY="" \
    MINIO_SECURE="false"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
