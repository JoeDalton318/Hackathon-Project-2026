from fastapi import APIRouter, Depends, HTTPException, status

from core.jwt import create_access_token, get_current_user
from models.user import UserRecord
from schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserOut
from services import auth_service
from schemas.response import APIResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest):
    user = await auth_service.create_user(
        email=body.email,
        password=body.password,
        nom=body.nom,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un compte existe déjà avec cet email",
        )
    return APIResponse(data=UserOut(
        user_id=user.user_id,
        email=user.email,
        nom=user.nom,
        role=user.role,
    ).model_dump())


@router.post("/login")
async def login(body: LoginRequest):
    user = await auth_service.authenticate_user(body.email, body.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect",
        )
    token = create_access_token({"user_id": user.user_id, "email": user.email})
    return APIResponse(data=TokenResponse(
        token=token,
        user=UserOut(
            user_id=user.user_id,
            email=user.email,
            nom=user.nom,
            role=user.role,
        ),
    ).model_dump())


@router.get("/me")
async def me(current_user: UserRecord = Depends(get_current_user)):
    return APIResponse(data=UserOut(
        user_id=current_user.user_id,
        email=current_user.email,
        nom=current_user.nom,
        role=current_user.role,
    ).model_dump())

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(current_user: UserRecord = Depends(get_current_user)):
    pass
