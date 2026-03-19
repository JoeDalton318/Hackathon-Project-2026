from uuid import uuid4

from models.user import UserRecord, UserRole
from database.mongo import get_db
from core.jwt import hash_password, verify_password

COLLECTION = "users"


async def create_user(email: str, password: str, nom: str) -> UserRecord | None:
    db = get_db()
    existing = await db[COLLECTION].find_one({"email": email})
    if existing:
        return None
    record = UserRecord(
        user_id=str(uuid4()),
        email=email,
        hashed_password=hash_password(password),
        nom=nom,
    )
    await db[COLLECTION].insert_one(record.model_dump())
    return record


async def authenticate_user(email: str, password: str) -> UserRecord | None:
    db = get_db()
    doc = await db[COLLECTION].find_one({"email": email})
    if doc is None:
        return None
    doc.pop("_id", None)
    user = UserRecord(**doc)
    if not verify_password(password, user.hashed_password):
        return None
    return user


async def get_user_by_id(user_id: str) -> UserRecord | None:
    db = get_db()
    doc = await db[COLLECTION].find_one({"user_id": user_id})
    if doc is None:
        return None
    doc.pop("_id", None)
    return UserRecord(**doc)