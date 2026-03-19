from fastapi import APIRouter, status

from schemas.pipeline import PipelineCallbackPayload
from services import document_service
from services.ws_manager import ws_manager

router = APIRouter(prefix="/internal/pipeline", tags=["internal"])


@router.post("/result", status_code=status.HTTP_204_NO_CONTENT)
async def pipeline_result(payload: PipelineCallbackPayload):
    await document_service.update_from_callback(payload)
    await ws_manager.broadcast(
        payload.document_id,
        {
            "document_id": payload.document_id,
            "status": payload.status,
            "document_type": payload.document_type,
            "alerts": payload.alerts,
            "signals": payload.signals,
        },
    )