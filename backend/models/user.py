from datetime import datetime, timezone
from enum import StrEnum, auto

from pydantic import BaseModel, Field


class UserRole(StrEnum):
    ADMIN = auto()
    USER = auto()


class UserRecord(BaseModel):
    user_id: str
    email: str
    hashed_password: str
    nom: str
    role: UserRole = UserRole.USER
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
