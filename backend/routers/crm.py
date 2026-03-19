from fastapi import APIRouter, HTTPException, status

from schemas.crm import SupplierOut
from services import document_service
from schemas.response import APIResponse

router = APIRouter(prefix="/crm", tags=["crm"])


@router.get("/supplier/{siret}")
async def get_supplier(siret: str):
    documents = await document_service.get_supplier_documents(siret)
    if not documents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Supplier not found"
        )

    merged: dict = {}
    for doc in documents:
        merged.update(doc.extracted_data)

    titulaire = merged.get("titulaire_compte") or {}
    adresse_obj = titulaire.get("adresse") or {}

    return APIResponse(
        data=SupplierOut(
            siret=siret,
            supplier_name=(
                merged.get("supplier_name") or titulaire.get("raison_sociale")
            ),
            iban=merged.get("iban"),
            address=(
                merged.get("address")
                or adresse_obj.get("adresse")
                or adresse_obj.get("code_postal")
            ),
            tva_number=(
                merged.get("tva_number") or titulaire.get("tva_intracommunautaire")
            ),
            decision=merged.get("decision"),
            documents=[
                {
                    "document_id": d.document_id,
                    "type": d.document_type,
                    "status": d.status,
                }
                for d in documents
            ],
        ).model_dump()
    )
