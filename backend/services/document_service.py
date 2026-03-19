from datetime import datetime, timezone
from uuid import uuid4

from models.document import DocumentRecord, DocumentStatus, DocumentType
from database.mongo import get_db
from schemas.pipeline import PipelineCallbackPayload

COLLECTION = "documents"


async def create_record(
    user_id: str, filename: str, mime_type: str, minio_path: str
) -> DocumentRecord:
    record = DocumentRecord(
        document_id=str(uuid4()),
        user_id=user_id,
        original_filename=filename,
        mime_type=mime_type,
        minio_path=minio_path,
    )
    db = get_db()
    await db[COLLECTION].insert_one(record.model_dump())
    return record


async def get_record(
    document_id: str, user_id: str | None = None
) -> DocumentRecord | None:
    db = get_db()
    query: dict = {"document_id": document_id}
    if user_id:
        query["user_id"] = user_id
    doc = await db[COLLECTION].find_one(query)
    if doc is None:
        return None
    doc.pop("_id", None)
    return DocumentRecord(**doc)


async def update_from_callback(payload: PipelineCallbackPayload) -> None:
    db = get_db()
    update: dict = {
        "status": payload.status,
        "updated_at": datetime.now(timezone.utc),
    }
    if payload.document_type is not None:
        update["document_type"] = payload.document_type
    if payload.decision is not None:
        update["decision"] = payload.decision
    if payload.extracted_data:
        update["extracted_data"] = payload.extracted_data
    if payload.alerts:
        update["anomalies"] = payload.alerts
    if payload.signals:
        update["signals"] = payload.signals

    await db[COLLECTION].update_one(
        {"document_id": payload.document_id},
        {"$set": update},
    )


async def list_records(
    user_id: str,
    status: DocumentStatus | None = None,
    document_type: DocumentType | None = None,
    skip: int = 0,
    limit: int = 20,
) -> tuple[int, list[DocumentRecord]]:
    db = get_db()
    query: dict = {"user_id": user_id}
    if status:
        query["status"] = status
    if document_type:
        query["document_type"] = document_type

    total = await db[COLLECTION].count_documents(query)
    cursor = db[COLLECTION].find(query).skip(skip).limit(limit)
    docs = []
    async for doc in cursor:
        doc.pop("_id", None)
        docs.append(DocumentRecord(**doc))
    return total, docs


async def get_supplier_documents(siret: str) -> list[DocumentRecord]:
    db = get_db()
    cursor = db[COLLECTION].find({"extracted_data.siret": siret})
    docs = []
    async for doc in cursor:
        doc.pop("_id", None)
        docs.append(DocumentRecord(**doc))
    return docs


async def update_minio_path(document_id: str, minio_path: str) -> None:
    db = get_db()
    await db[COLLECTION].update_one(
        {"document_id": document_id},
        {"$set": {"minio_path": minio_path, "updated_at": datetime.now(timezone.utc)}},
    )


async def update_status(document_id: str, new_status: DocumentStatus) -> None:
    db = get_db()
    await db[COLLECTION].update_one(
        {"document_id": document_id},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc)}},
    )


async def delete_record(document_id: str, user_id: str | None = None) -> None:
    db = get_db()
    query: dict = {"document_id": document_id}
    if user_id:
        query["user_id"] = user_id
    await db[COLLECTION].delete_one(query)
