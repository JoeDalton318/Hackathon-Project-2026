from pydantic import AliasChoices, BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    email: str
    password: str
    nom: str = Field(validation_alias=AliasChoices("nom", "name"))


class TokenResponse(BaseModel):
    token: str
    user: "UserOut"


class UserOut(BaseModel):
    user_id: str
    email: str
    nom: str
    role: str


TokenResponse.model_rebuild()