from pydantic import BaseModel


class AnomalyOut(BaseModel):
    type: str
    severity: str
    description: str
    document_ids: list[str] = []


class ComplianceDossierOut(BaseModel):
    siret: str
    is_compliant: bool
    anomalies: list[AnomalyOut] = []
    documents_summary: list[dict] = []