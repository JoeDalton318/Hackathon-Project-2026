from uuid import uuid4

from core.jwt import hash_password, verify_password
from database.mongo import get_db
from models.user import UserRecord

COLLECTION = "users"


async def create_user(email: str, password: str, nom: str = "") -> UserRecord | None:
    """Crée un utilisateur (data-architecture: email, password_hash, nom, created_at)."""
    db = get_db()
    existing = await db[COLLECTION].find_one({"email": email})
    if existing:
        return None
    record = UserRecord(
        user_id=str(uuid4()),
        email=email,
        password_hash=hash_password(password),
        nom=nom,
    )
    data = record.model_dump()
    await db[COLLECTION].insert_one(data)
    record.password_hash = None
    return record


async def authenticate_user(email: str, password: str) -> UserRecord | None:
    db = get_db()
    doc = await db[COLLECTION].find_one({"email": email})
    if doc is None:
        return None
    if not verify_password(password, doc.get("password_hash", "")):
        return None
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    return UserRecord(**doc)


async def get_user_by_id(user_id: str) -> UserRecord | None:
    db = get_db()
    doc = await db[COLLECTION].find_one({"user_id": user_id})
    if doc is None:
        return None
    doc.pop("_id", None)
    doc.pop("password_hash", None)
    return UserRecord(**doc)
