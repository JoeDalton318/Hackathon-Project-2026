import zipfile
import io as _io
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status, Depends
from fastapi.responses import RedirectResponse
from schemas.response import APIResponse
from core.jwt import get_current_user
from models.user import UserRecord

from models.document import DocumentStatus, DocumentType
from schemas.document import DocumentListOut, DocumentOut, UploadResponse
from services import airflow_service, document_service, minio_service

router = APIRouter(prefix="/documents", tags=["documents"])

ALLOWED_MIME_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/tiff"}


@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_documents(
    files: list[UploadFile] = File(...),
    current_user: UserRecord = Depends(get_current_user),
):
    responses = []
    for file in files:
        if file.content_type not in ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Type non supporté : {file.content_type}",
            )
        data = await file.read()
        record = await document_service.create_record(
            user_id=current_user.user_id,  # ajout
            filename=file.filename,
            mime_type=file.content_type,
            minio_path="",
        )
        minio_path = await minio_service.upload_raw(
            document_id=record.document_id,
            filename=file.filename,
            data=data,
            content_type=file.content_type,
        )
        await document_service.update_minio_path(record.document_id, minio_path)
        await airflow_service.trigger_pipeline(record.document_id)
        responses.append(
            UploadResponse(
                document_id=record.document_id,
                filename=record.original_filename,
                status=record.status,
            ).model_dump()
        )
    return APIResponse(data={"documents": responses})


@router.get("")
@router.get("/")
async def list_documents(
    status_filter: DocumentStatus | None = Query(default=None, alias="status"),
    document_type: DocumentType | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: UserRecord = Depends(get_current_user),
):
    skip = (page - 1) * limit
    total, records = await document_service.list_records(
        user_id=current_user.user_id,
        status=status_filter,
        document_type=document_type,
        skip=skip,
        limit=limit,
    )

    items = [
        DocumentOut(**record.model_dump()).model_dump()
        for record in records
    ]

    return APIResponse(
        data=DocumentListOut(
            total=total,
            page=page,
            limit=limit,
            items=items,
        ).model_dump()
    )


@router.get("/{document_id}")
async def get_document(
    document_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    record = await document_service.get_record(
        document_id, user_id=current_user.user_id
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable"
        )
    return APIResponse(data=DocumentOut(**record.model_dump()).model_dump())


@router.get("/{document_id}/anomalies")
async def get_anomalies(
    document_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    record = await document_service.get_record(
        document_id, user_id=current_user.user_id
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable"
        )
    return APIResponse(data={"document_id": document_id, "anomalies": record.anomalies})


@router.get("/{document_id}/download")
async def download_document(
    document_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    record = await document_service.get_record(
        document_id, user_id=current_user.user_id
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable"
        )
    url = minio_service.get_presigned_url(record.minio_path)
    return RedirectResponse(url=url)


@router.get("/{document_id}/status")
async def get_document_status(
    document_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    record = await document_service.get_record(
        document_id, user_id=current_user.user_id
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable"
        )
    return APIResponse(
        data={
            "document_id": document_id,
            "status": record.status,
            "document_type": record.document_type,
            "updated_at": record.updated_at.isoformat(),
        }
    )


@router.post("/{document_id}/process")
async def process_document(
    document_id: str,
    current_user: UserRecord = Depends(get_current_user),
):
    record = await document_service.get_record(
        document_id, user_id=current_user.user_id
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable"
        )
    triggered = await airflow_service.trigger_pipeline(document_id)
    if not triggered:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Impossible de joindre Airflow",
        )
    await document_service.update_status(document_id, DocumentStatus.PENDING)
    return APIResponse(
        data={"document_id": document_id, "status": DocumentStatus.PENDING}
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str, current_user: UserRecord = Depends(get_current_user)
):
    record = await document_service.get_record(
        document_id, user_id=current_user.user_id
    )
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document introuvable"
        )
    await document_service.delete_record(document_id, user_id=current_user.user_id)


@router.post("/upload-folder", status_code=status.HTTP_202_ACCEPTED)
async def upload_folder(file: UploadFile = File(...)):
    if file.content_type not in {"application/zip", "application/x-zip-compressed"}:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Seuls les fichiers ZIP sont acceptés",
        )
    data = await file.read()
    responses = []
    with zipfile.ZipFile(_io.BytesIO(data)) as zf:
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
                filename=filename,
                mime_type=mime_type,
                minio_path="",
            )
            minio_path = await minio_service.upload_raw(
                document_id=record.document_id,
                filename=filename,
                data=file_data,
                content_type=mime_type,
            )
            await document_service.update_minio_path(record.document_id, minio_path)
            await airflow_service.trigger_pipeline(record.document_id)
            responses.append(
                UploadResponse(
                    document_id=record.document_id,
                    filename=filename,
                    status=record.status,
                ).model_dump()
            )
    if not responses:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Aucun fichier valide trouvé dans le ZIP",
        )
    return APIResponse(data={"documents": responses})
