from datetime import datetime

from pydantic import BaseModel


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    statut_traitement: str


class DocumentOut(BaseModel):
    """Aligné data-architecture: champs documents."""
    document_id: str
    user_id: str
    nom_fichier_original: str
    type_mime: str
    chemin_minio_bronze: str
    chemin_minio_silver: str
    statut_traitement: str
    job_id: str | None
    type_document_extrait: str | None
    resultat_extraction: dict
    texte_ocr: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListOut(BaseModel):
    total: int
    page: int
    limit: int
    items: list[DocumentOut]
