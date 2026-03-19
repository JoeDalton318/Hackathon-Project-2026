from fastapi import Header, HTTPException, status

from app.config import settings


async def verify_internal_secret(x_internal_secret: str = Header(...)) -> None:
    if x_internal_secret != settings.INTERNAL_API_SECRET:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")