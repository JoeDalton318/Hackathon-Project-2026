from datetime import datetime

from pydantic import BaseModel, Field


class UserRecord(BaseModel):
    """Aligné data-architecture: users (email, password_hash, nom, created_at)."""
    user_id: str
    email: str
    password_hash: str | None = None  # non exposé dans get_current_user
    nom: str = ""
    role: str = "USER"  # optionnel, non dans le schéma data-arch
    created_at: datetime = Field(default_factory=datetime.utcnow)
