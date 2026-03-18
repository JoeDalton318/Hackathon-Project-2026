from datetime import datetime, timezone
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
    INVOICE = auto()
    QUOTE = auto()
    KBIS = auto()
    RIB = auto()
    URSSAF = auto()
    SIRET_CERT = auto()
    UNKNOWN = auto()


class DocumentRecord(BaseModel):
    user_id: str
    document_id: str
    original_filename: str
    mime_type: str
    minio_path: str
    status: DocumentStatus = DocumentStatus.PENDING
    document_type: DocumentType = DocumentType.UNKNOWN
    decision: str | None = None
    extracted_data: dict = Field(default_factory=dict)
    anomalies: list[dict] = Field(default_factory=list)
    signals: list[dict] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
