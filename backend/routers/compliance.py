from fastapi import APIRouter, HTTPException, status

from schemas.compliance import AnomalyOut, ComplianceDossierOut
from schemas.response import APIResponse
from services import document_service

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.get("/dossier/{siret}")
async def get_dossier(siret: str):
    documents = await document_service.get_supplier_documents(siret)
    if not documents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Dossier introuvable")
    all_anomalies: list[AnomalyOut] = []
    for doc in documents:
        signales = doc.resultat_extraction.get("signales", [])
        for anomaly in signales:
            if isinstance(anomaly, dict):
                all_anomalies.append(AnomalyOut(
                    type=anomaly.get("type", ""),
                    severity=anomaly.get("severity", ""),
                    description=anomaly.get("description", ""),
                    document_ids=[doc.document_id],
                ))
    return APIResponse(data=ComplianceDossierOut(
        siret=siret,
        is_compliant=len(all_anomalies) == 0,
        anomalies=all_anomalies,
        documents_summary=[
            {"document_id": d.document_id, "type": d.type_document_extrait, "statut": d.statut_traitement}
            for d in documents
        ],
    ).model_dump())
