from contextlib import asynccontextmanager

from fastapi import FastAPI, APIRouter, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from schemas.response import APIError

from app.config import settings
from core.logging import setup_logging

from database.minio import init_buckets
from database.mongo import close_mongo, connect_mongo, create_indexes
from routers import compliance, crm, documents, pipeline, ws, auth


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await connect_mongo()
    await create_indexes()
    # Créer les buckets MinIO (RAW, CLEAN, CURATED) s’ils n’existent pas, pour éviter des erreurs au premier upload
    init_buckets()
    yield
    await close_mongo()


app = FastAPI(
    title="Hackathon 2026 — Document Processing API",
    version="1.0.0",
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api")
api_router.include_router(documents.router)
api_router.include_router(pipeline.router)
api_router.include_router(ws.router)
api_router.include_router(crm.router)
api_router.include_router(compliance.router)
api_router.include_router(auth.router)

app.include_router(api_router)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=APIError(
            error=exc.detail,
            code=f"HTTP_{exc.status_code}",
        ).model_dump(),
    )
