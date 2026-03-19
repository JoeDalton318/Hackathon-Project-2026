"""
FastAPI Backend - Point d'entrée
À personnaliser par l'équipe backend
"""
import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


TOKEN_SECRET = secrets.token_hex(32)
TOKEN_TTL_SECONDS = 24 * 60 * 60
bearer_scheme = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


USERS: dict[str, dict[str, str]] = {}
ACTIVE_WS_CONNECTIONS: list[WebSocket] = []


def _base64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _base64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(f"{data}{padding}")


def hash_password(password: str, salt: str | None = None) -> str:
    current_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        current_salt.encode("utf-8"),
        200_000,
    )
    return f"{current_salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, digest = stored_hash.split("$", maxsplit=1)
    except ValueError:
        return False

    candidate = hash_password(password, salt).split("$", maxsplit=1)[1]
    return hmac.compare_digest(candidate, digest)


def create_access_token(email: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + TOKEN_TTL_SECONDS,
    }

    header_part = _base64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_part = _base64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_part}.{payload_part}".encode("utf-8")
    signature = hmac.new(TOKEN_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_part = _base64url_encode(signature)
    return f"{header_part}.{payload_part}.{signature_part}"


def decode_access_token(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format")

    header_part, payload_part, signature_part = parts
    signing_input = f"{header_part}.{payload_part}".encode("utf-8")
    expected_signature = hmac.new(TOKEN_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    provided_signature = _base64url_decode(signature_part)

    if not hmac.compare_digest(expected_signature, provided_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token signature")

    try:
        payload = json.loads(_base64url_decode(payload_part).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    if int(payload.get("exp", 0)) < int(time.time()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")

    return payload


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> dict:
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    payload = decode_access_token(credentials.credentials)
    email = payload.get("sub")
    if not email or email not in USERS:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid user")

    return USERS[email]


async def broadcast_ws_event(event_type: str, payload: dict) -> None:
    if not ACTIVE_WS_CONNECTIONS:
        return

    disconnected: list[WebSocket] = []
    message = {"type": event_type, "payload": payload, "timestamp": int(time.time())}

    for connection in ACTIVE_WS_CONNECTIONS:
        try:
            await connection.send_json(message)
        except Exception:
            disconnected.append(connection)

    if disconnected:
        for connection in disconnected:
            if connection in ACTIVE_WS_CONNECTIONS:
                ACTIVE_WS_CONNECTIONS.remove(connection)


DOCUMENTS: list[dict] = []


def build_document_record(file: UploadFile) -> dict:
    next_id = len(DOCUMENTS) + 1
    return {
        "id": next_id,
        "filename": file.filename,
        "documentType": "unknown",
        "supplier": "Unknown Supplier",
        "siren": "",
        "siret": "",
        "extractedAmount": 0.0,
        "currency": "EUR",
        "validationStatus": "review",
        "inconsistencies": [],
    }

app = FastAPI(
    title="Hackathon Data Engineering API",
    description="API pour l'upload de documents et l'interface avec la BDD",
    version="1.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # À adapter en production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """Endpoint de santé"""
    return {"status": "ok", "message": "API Hackathon is running"}

@app.get("/health")
async def health_check():
    """Vérification de l'état de l'API"""
    return {"status": "healthy"}


@app.post("/auth/register")
async def register(payload: RegisterRequest):
    """Crée un utilisateur et retourne un token d'accès."""
    email = payload.email.lower().strip()
    if email in USERS:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    if len(payload.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")

    USERS[email] = {
        "name": payload.name.strip(),
        "email": email,
        "password_hash": hash_password(payload.password),
    }

    token = create_access_token(email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "name": USERS[email]["name"],
            "email": USERS[email]["email"],
        },
    }


@app.post("/auth/login")
async def login(payload: LoginRequest):
    """Authentifie un utilisateur et retourne un token d'accès."""
    email = payload.email.lower().strip()
    user = USERS.get(email)

    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(email)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "name": user["name"],
            "email": user["email"],
        },
    }


@app.get("/documents")
async def list_documents(_: dict = Depends(get_current_user)):
    """Retourne la liste des documents disponibles pour le dashboard."""
    return {"data": DOCUMENTS}


@app.post("/upload")
async def upload_documents(files: list[UploadFile] = File(...), _: dict = Depends(get_current_user)):
    """Reçoit des fichiers et retourne un résumé pour le frontend."""
    uploaded = []
    for file in files:
        document = build_document_record(file)
        DOCUMENTS.append(document)
        uploaded.append(
            {
                "id": document["id"],
                "filename": file.filename,
                "contentType": file.content_type,
            }
        )

    await broadcast_ws_event(
        "documents_updated",
        {
            "uploadedCount": len(uploaded),
            "files": uploaded,
        },
    )

    return {"data": uploaded, "message": f"{len(uploaded)} file(s) uploaded"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str = Query(default="")):
    if not token:
        await websocket.close(code=1008, reason="Missing token")
        return

    try:
        payload = decode_access_token(token)
        email = payload.get("sub")
        if not email or email not in USERS:
            await websocket.close(code=1008, reason="Invalid user")
            return
    except HTTPException:
        await websocket.close(code=1008, reason="Invalid token")
        return

    await websocket.accept()
    ACTIVE_WS_CONNECTIONS.append(websocket)

    await websocket.send_json(
        {
            "type": "connected",
            "payload": {"message": "WebSocket connected", "email": email},
            "timestamp": int(time.time()),
        }
    )

    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_json(
                    {
                        "type": "pong",
                        "payload": {"message": "pong"},
                        "timestamp": int(time.time()),
                    }
                )
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in ACTIVE_WS_CONNECTIONS:
            ACTIVE_WS_CONNECTIONS.remove(websocket)

# TODO: Ajouter vos endpoints ici
# - Upload de documents
# - Récupération des données
# - etc.
