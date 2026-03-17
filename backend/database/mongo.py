from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

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
    """Crée les index recommandés data-architecture (users: email unique; documents: user_id, statut_traitement)."""
    db = get_db()
    await db[COLLECTION_USERS].create_index([("email", 1)], unique=True)
    await db[COLLECTION_DOCUMENTS].create_index([("user_id", 1), ("created_at", -1)])
    await db[COLLECTION_DOCUMENTS].create_index([("statut_traitement", 1)])
    await db[COLLECTION_DOCUMENTS].create_index([("user_id", 1), ("statut_traitement", 1)])
