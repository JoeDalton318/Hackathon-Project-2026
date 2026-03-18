from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    nom: str


class TokenResponse(BaseModel):
    token: str
    user: "UserOut"


class UserOut(BaseModel):
    user_id: str
    email: str
    nom: str
    role: str


TokenResponse.model_rebuild()