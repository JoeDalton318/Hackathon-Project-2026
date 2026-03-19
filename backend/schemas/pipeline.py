from pydantic import AliasChoices, BaseModel, Field

from models.document import DocumentStatus, DocumentType


class PipelineCallbackPayload(BaseModel):
    document_id: str
    status: str
    document_type: str | None = None
    decision: str | None = None
    extracted_data: dict = Field(default_factory=dict)
    alerts: list[dict] = Field(
        default_factory=list,
        validation_alias=AliasChoices("alerts", "anomalies"),
    )
    signals: list[dict] = Field(default_factory=list)
    batch_id: str | None = None
    error_message: str | None = None
