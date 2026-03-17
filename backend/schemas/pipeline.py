from pydantic import BaseModel


class PipelineCallbackPayload(BaseModel):
    """Payload callback Airflow → Backend (data-architecture: mise à jour documents)."""
    document_id: str
    status: str  # en_attente | en_cours | termine | erreur
    document_type: str | None = None  # facture, devis, avoir, attestation_siret, etc.
    extracted_data: dict = {}  # → resultat_extraction.donnees
    anomalies: list[dict] = []  # → resultat_extraction.signales
    texte_ocr: str | None = None
    error_message: str | None = None
