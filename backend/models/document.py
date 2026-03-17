from datetime import datetime

from pydantic import BaseModel, Field


# Statuts alignés data-architecture: en_attente, en_cours, termine, erreur


class DocumentRecord(BaseModel):
    """Aligné data-architecture: documents (user_id, nom_fichier_original, chemin_minio_bronze/silver, statut_traitement, resultat_extraction, etc.)."""
    document_id: str
    user_id: str
    nom_fichier_original: str
    type_mime: str = ""
    chemin_minio_bronze: str = ""
    chemin_minio_silver: str = ""
    statut_traitement: str = "en_attente"
    job_id: str | None = None
    type_document_extrait: str | None = None  # facture, devis, avoir, attestation_siret, etc.
    resultat_extraction: dict = Field(default_factory=dict)  # { type, confidence, donnees, signales }
    texte_ocr: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
