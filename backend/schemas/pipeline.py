from pydantic import BaseModel

from models.document import DocumentStatus, DocumentType


class PipelineCallbackPayload(BaseModel):
    document_id: str
    status: str
    document_type: str | None = None
    decision: str | None = None
    extracted_data: dict = {}
    alerts: list[dict] = []
    signals: list[dict] = []
    batch_id: str | None = None
    error_message: str | None = None
