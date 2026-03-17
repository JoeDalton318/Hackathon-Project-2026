from fastapi import APIRouter, Depends, status

from core.security import verify_internal_secret
from schemas.pipeline import PipelineCallbackPayload
from services import document_service
from services.ws_manager import ws_manager

router = APIRouter(prefix="/internal/pipeline", tags=["internal"])


@router.post("/result", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(verify_internal_secret)])
async def pipeline_result(payload: PipelineCallbackPayload):
    await document_service.update_from_callback(payload)
    await ws_manager.broadcast(
        payload.document_id,
        {
            "document_id": payload.document_id,
            "statut_traitement": payload.status,
            "type_document_extrait": payload.document_type,
            "anomalies": payload.anomalies,
        },
    )
