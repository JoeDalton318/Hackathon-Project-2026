from datetime import datetime
from enum import StrEnum, auto

from pydantic import BaseModel, Field


class DocumentStatus(StrEnum):
    PENDING = auto()
    PROCESSING = auto()
    OCR_DONE = auto()
    EXTRACTION_DONE = auto()
    DONE = auto()
    ERROR = auto()


class DocumentType(StrEnum):
    FACTURE = auto()
    DEVIS = auto()
    KBIS = auto()
    RIB = auto()
    ATTESTATION_URSSAF = auto()
    ATTESTATION_SIRET = auto()
    UNKNOWN = auto()


class DocumentRecord(BaseModel):
    user_id: str
    document_id: str
    original_filename: str
    mime_type: str
    minio_path: str
    status: DocumentStatus = DocumentStatus.PENDING
    document_type: DocumentType = DocumentType.UNKNOWN
    extracted_data: dict = Field(default_factory=dict)
    anomalies: list[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
