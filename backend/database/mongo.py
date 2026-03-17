from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from typing import cast

from app.config import settings

_client: AsyncIOMotorClient | None = None


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