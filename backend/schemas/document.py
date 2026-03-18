from datetime import datetime

from pydantic import BaseModel

from models.document import DocumentStatus, DocumentType


class UploadResponse(BaseModel):
    document_id: str
    filename: str
    status: DocumentStatus


class DocumentOut(BaseModel):
    document_id: str
    original_filename: str
    status: DocumentStatus
    document_type: DocumentType
    extracted_data: dict
    anomalies: list[dict]
    created_at: datetime
    updated_at: datetime


class DocumentListOut(BaseModel):
    total: int
    page: int
    limit: int
    items: list[DocumentOut]