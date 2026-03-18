from fastapi import APIRouter, HTTPException, status

from schemas.compliance import AnomalyOut, ComplianceDossierOut
from services import document_service
from schemas.response import APIResponse
router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/dossier/{siret}")
async def get_dossier(siret: str):
    documents = await document_service.get_supplier_documents(siret)
    if not documents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier introuvable")
    all_anomalies: list[AnomalyOut] = []
    for doc in documents:
        for anomaly in doc.anomalies:
            all_anomalies.append(AnomalyOut(**anomaly, document_ids=[doc.document_id]))
    return APIResponse(data=ComplianceDossierOut(
        siret=siret,
        is_compliant=len(all_anomalies) == 0,
        anomalies=all_anomalies,
        documents_summary=[
            {"document_id": d.document_id, "type": d.document_type, "status": d.status}
            for d in documents
        ],
    ).model_dump())