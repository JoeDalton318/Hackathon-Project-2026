import io
import zipfile
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import RedirectResponse

from core.jwt import get_current_user
from models.user import UserRecord
from schemas.document import DocumentListOut, DocumentOut, UploadResponse
from schemas.response import APIResponse
from services import airflow_service, document_service, minio_service

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/tiff"}


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_documents(
    files: list[UploadFile] = File(...),
    current_user: UserRecord = Depends(get_current_user),
):
    user_id = current_user.user_id
    batch_id = f"batch_{uuid4().hex[:12]}"
    responses = []
    for file in files:
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Type non supporté : {file.content_type}",
            )
        data = await file.read()
        record = await document_service.create_record(
            user_id=user_id,
            filename=file.filename,
            mime_type=file.content_type or "",
            chemin_minio_bronze="",
        )
        minio_path = await minio_service.upload_raw(
            user_id=user_id,
            document_id=record.document_id,
            filename=file.filename,
            data=data,
            content_type=file.content_type or "",
            batch_id=batch_id,
        )
        await document_service.update_minio_bronze(record.document_id, minio_path)
        await airflow_service.trigger_pipeline(record.document_id)
        responses.append(UploadResponse(
            document_id=record.document_id,
            filename=record.nom_fichier_original,
            statut_traitement=record.statut_traitement,
        ).model_dump())
    return APIResponse(data={"documents": responses})


@router.get("/")
async def list_documents(
    current_user: UserRecord = Depends(get_current_user),
    statut: str | None = Query(default=None, alias="statut_traitement"),
    type_document: str | None = Query(default=None, alias="type_document_extrait"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
):
    skip = (page - 1) * limit
    total, records = await document_service.list_records(
        user_id=current_user.user_id,
        statut=statut,
        type_document=type_document,
        skip=skip,
        limit=limit,
    )
    return APIResponse(data=DocumentListOut(
        total=total,
        page=page,
        limit=limit,
        items=[DocumentOut(**r.model_dump()).model_dump() for r in records],
    ).model_dump())


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    record = await document_service.get_record(document_id, user_id=current_user.user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    return APIResponse(data=DocumentOut(**record.model_dump()).model_dump())


@router.get("/{document_id}/anomalies")
async def get_anomalies(
    document_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    record = await document_service.get_record(document_id, user_id=current_user.user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    anomalies = record.resultat_extraction.get("signales", [])
    return APIResponse(data={"document_id": document_id, "anomalies": anomalies})


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    record = await document_service.get_record(document_id, user_id=current_user.user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    url = minio_service.get_presigned_url(record.chemin_minio_bronze)
    return RedirectResponse(url=url)


@router.get("/{document_id}/status")
async def get_document_status(
    document_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    record = await document_service.get_record(document_id, user_id=current_user.user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    return APIResponse(data={
        "document_id": document_id,
        "statut_traitement": record.statut_traitement,
        "type_document_extrait": record.type_document_extrait,
        "updated_at": record.updated_at.isoformat(),
    })


@router.post("/{document_id}/process")
async def process_document(
    document_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    record = await document_service.get_record(document_id, user_id=current_user.user_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")
    triggered = await airflow_service.trigger_pipeline(document_id)
    if not triggered:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Impossible de joindre Airflow",
        )
    await document_service.update_statut(document_id, "en_attente")
    return APIResponse(data={"document_id": document_id, "statut_traitement": "en_attente"})


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    deleted = await document_service.delete_record(document_id, user_id=current_user.user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable")


@router.post("/upload-folder", status_code=status.HTTP_202_ACCEPTED)
async def upload_folder(
    file: UploadFile = File(...),
    current_user: UserRecord = Depends(get_current_user),
):
    if file.content_type not in {"application/zip", "application/x-zip-compressed"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Seuls les fichiers ZIP sont acceptés",
        )
    data = await file.read()
    user_id = current_user.user_id
    batch_id = f"batch_{uuid4().hex[:12]}"
    responses = []
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for name in zf.namelist():
            if name.endswith("/"):
                continue
            ext = name.rsplit(".", 1)[-1].lower()
            mime_map = {
                "pdf": "application/pdf",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "tiff": "image/tiff",
            }
            mime_type = mime_map.get(ext)
            if mime_type is None:
                continue
            file_data = zf.read(name)
            filename = name.split("/")[-1]
            record = await document_service.create_record(
                user_id=user_id,
                filename=filename,
                mime_type=mime_type,
                chemin_minio_bronze="",
            )
            minio_path = await minio_service.upload_raw(
                user_id=user_id,
                document_id=record.document_id,
                filename=filename,
                data=file_data,
                content_type=mime_type,
                batch_id=batch_id,
            )
            await document_service.update_minio_bronze(record.document_id, minio_path)
            await airflow_service.trigger_pipeline(record.document_id)
            responses.append(UploadResponse(
                document_id=record.document_id,
                filename=filename,
                statut_traitement=record.statut_traitement,
            ).model_dump())
    if not responses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun fichier valide trouvé dans le ZIP",
        )
    return APIResponse(data={"documents": responses})
