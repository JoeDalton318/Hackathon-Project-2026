from setuptools import setup, find_packages

setup(
    name="nlp-ocr",
    version="1.0.0",
    description="Pipeline OCR/NER pour documents administratifs français — Hackathon 2026",
    author="Juba",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "pytesseract>=0.3.10",
        "easyocr>=1.7.1",
        "PyMuPDF>=1.24.3",
        "opencv-python-headless>=4.9.0",
        "Pillow>=10.3.0",
        "numpy>=1.26.0",
        "spacy>=3.7.4",
        "dateparser>=1.2.0",
        "pydantic>=2.7.1",
        "fastapi>=0.111.0",
        "uvicorn[standard]>=0.29.0",
        "python-multipart>=0.0.9",
        "minio>=7.2.7",
        "faker>=24.11.0",
        "fpdf2>=2.7.9",
        "python-dotenv>=1.0.1",
    ],
)
