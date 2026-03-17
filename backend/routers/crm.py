from fastapi import APIRouter, HTTPException, status

from schemas.crm import SupplierOut
from schemas.response import APIResponse
from services import document_service

router = APIRouter(prefix="/crm", tags=["crm"])


@router.get("/supplier/{siret}")
async def get_supplier(siret: str):
    documents = await document_service.get_supplier_documents(siret)
    if not documents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fournisseur introuvable")
    merged: dict = {}
    for doc in documents:
        donnees = doc.resultat_extraction.get("donnees", {})
        merged.update(donnees)
    return APIResponse(data=SupplierOut(
        siret=siret,
        raison_sociale=merged.get("raison_sociale"),
        iban=merged.get("iban"),
        adresse=merged.get("adresse"),
        tva_intracommunautaire=merged.get("tva_intracommunautaire"),
        conformite_status=merged.get("conformite_status"),
        documents=[
            {"document_id": d.document_id, "type": d.type_document_extrait, "statut": d.statut_traitement}
            for d in documents
        ],
    ).model_dump())
