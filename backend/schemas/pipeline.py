from pydantic import BaseModel

from models.document import DocumentStatus, DocumentType


class PipelineCallbackPayload(BaseModel):
    document_id: str
    status: DocumentStatus
    document_type: DocumentType | None = None
    extracted_data: dict = {}
    anomalies: list[dict] = []
    error_message: str | None = None