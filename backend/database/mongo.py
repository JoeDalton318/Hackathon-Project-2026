from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING

from app.config import settings

_client: AsyncIOMotorClient | None = None

COLLECTION_USERS = "users"
COLLECTION_DOCUMENTS = "documents"


async def connect_mongo() -> None:
    global _client
    _client = AsyncIOMotorClient(settings.MONGO_URL)


async def close_mongo() -> None:
    if _client:
        _client.close()


def get_db() -> AsyncIOMotorDatabase:
    if _client is None:
        raise RuntimeError("MongoDB client non initialisé")
    return _client[settings.MONGO_DB]


async def create_indexes() -> None:
    db = get_db()
    await db[COLLECTION_USERS].create_index([("email", ASCENDING)], unique=True)
    await db[COLLECTION_DOCUMENTS].create_index(
        [("user_id", ASCENDING), ("created_at", ASCENDING)]
    )
    await db[COLLECTION_DOCUMENTS].create_index([("status", ASCENDING)])
    await db[COLLECTION_DOCUMENTS].create_index(
        [("user_id", ASCENDING), ("status", ASCENDING)]
    )
