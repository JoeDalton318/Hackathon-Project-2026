from typing import Any

from pydantic import BaseModel


class APIResponse(BaseModel):
    success: bool = True
    data: Any = None


class APIError(BaseModel):
    success: bool = False
    error: str
    code: str