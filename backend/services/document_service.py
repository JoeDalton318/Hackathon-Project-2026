from datetime import datetime
from uuid import uuid4

from database.mongo import get_db
from models.document import DocumentRecord
from schemas.pipeline import PipelineCallbackPayload

COLLECTION = "documents"


async def create_record(
    user_id: str,
    filename: str,
    mime_type: str,
    chemin_minio_bronze: str = "",
) -> DocumentRecord:
    """Crée un document (data-architecture: statut_traitement en_attente)."""
    record = DocumentRecord(
        document_id=str(uuid4()),
        user_id=user_id,
        nom_fichier_original=filename,
        type_mime=mime_type,
        chemin_minio_bronze=chemin_minio_bronze,
        statut_traitement="en_attente",
    )
    db = get_db()
    await db[COLLECTION].insert_one(record.model_dump())
    return record


async def get_record(document_id: str, user_id: str | None = None) -> DocumentRecord | None:
    db = get_db()
    query: dict = {"document_id": document_id}
    if user_id is not None:
        query["user_id"] = user_id
    doc = await db[COLLECTION].find_one(query)
    if doc is None:
        return None
    doc.pop("_id", None)
    return DocumentRecord(**doc)


async def update_from_callback(payload: PipelineCallbackPayload) -> None:
    """Met à jour le document depuis le callback Airflow (resultat_extraction = { type, confidence, donnees, signales })."""
    db = get_db()
    resultat_extraction = {
        "type": payload.document_type or payload.extracted_data.get("type"),
        "confidence": payload.extracted_data.get("confidence"),
        "donnees": payload.extracted_data,
        "signales": payload.anomalies,
    }
    update: dict = {
        "statut_traitement": payload.status,
        "updated_at": datetime.utcnow(),
    }
    if payload.document_type is not None:
        update["type_document_extrait"] = payload.document_type
    update["resultat_extraction"] = resultat_extraction
    if payload.texte_ocr is not None:
        update["texte_ocr"] = payload.texte_ocr

    await db[COLLECTION].update_one(
        {"document_id": payload.document_id},
        {"$set": update},
    )


async def list_records(
    user_id: str,
    statut: str | None = None,
    type_document: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[int, list[DocumentRecord]]:
    db = get_db()
    query: dict = {"user_id": user_id}
    if statut:
        query["statut_traitement"] = statut
    if type_document:
        query["type_document_extrait"] = type_document

    total = await db[COLLECTION].count_documents(query)
    cursor = db[COLLECTION].find(query).sort("created_at", -1).skip(skip).limit(limit)
    docs = []
    async for doc in cursor:
        doc.pop("_id", None)
        docs.append(DocumentRecord(**doc))
    return total, docs


async def get_supplier_documents(siret: str) -> list[DocumentRecord]:
    """Documents dont resultat_extraction.donnees contient le SIRET (fournisseur ou racine)."""
    db = get_db()
    cursor = db[COLLECTION].find({
        "$or": [
            {"resultat_extraction.donnees.siret": siret},
            {"resultat_extraction.donnees.fournisseur.siret": siret},
        ]
    })
    docs = []
    async for doc in cursor:
        doc.pop("_id", None)
        docs.append(DocumentRecord(**doc))
    return docs


async def update_minio_bronze(document_id: str, chemin: str) -> None:
    db = get_db()
    await db[COLLECTION].update_one(
        {"document_id": document_id},
        {"$set": {"chemin_minio_bronze": chemin, "updated_at": datetime.utcnow()}},
    )


async def update_chemin_silver(document_id: str, chemin: str) -> None:
    db = get_db()
    await db[COLLECTION].update_one(
        {"document_id": document_id},
        {"$set": {"chemin_minio_silver": chemin, "updated_at": datetime.utcnow()}},
    )


async def update_statut(document_id: str, statut_traitement: str) -> None:
    db = get_db()
    await db[COLLECTION].update_one(
        {"document_id": document_id},
        {"$set": {"statut_traitement": statut_traitement, "updated_at": datetime.utcnow()}},
    )


async def delete_record(document_id: str, user_id: str | None = None) -> bool:
    db = get_db()
    query: dict = {"document_id": document_id}
    if user_id is not None:
        query["user_id"] = user_id
    result = await db[COLLECTION].delete_one(query)
    return result.deleted_count > 0
