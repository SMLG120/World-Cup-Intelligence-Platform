"""Authentication endpoints."""
from __future__ import annotations

import jwt
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import ValidationError

from app.core.deps import CurrentUser, DbSession
from app.core.security import (REFRESH, create_access_token,
                               create_refresh_token, decode_token,
                               hash_password, verify_password)
from app.models.user import User
from app.repositories.repos import UserRepository
from app.schemas.auth import (RefreshRequest, TokenPair, UserCreate, UserLogin, UserOut)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
def register(payload: UserCreate, db: DbSession) -> User:
    repo = UserRepository(db)
    if repo.get_by_email(payload.email):
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
    )
    return repo.add(user)


@router.post("/login", response_model=TokenPair)
async def login(request: Request, db: DbSession) -> TokenPair:
    """Password login.

    Accepts the OAuth2 form shape (`username` + `password`) used by Swagger and
    older frontend code, plus JSON (`email` + `password`) for local curl/dev use.
    """
    email, password = await _login_credentials(request)
    repo = UserRepository(db)
    user = repo.get_by_email(email)
    if (user is None or not user.hashed_password
            or not verify_password(password, user.hashed_password)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    return TokenPair(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id)),
    )


async def _login_credentials(request: Request) -> tuple[str, str]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type == "application/json":
        try:
            payload = UserLogin.model_validate(await request.json())
        except (ValueError, ValidationError):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Invalid login payload")
        return payload.email.lower(), payload.password

    form = await request.form()
    email = str(form.get("username") or form.get("email") or "").strip().lower()
    password = str(form.get("password") or "")
    if not email or not password:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Email and password are required")
    return email, password


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: DbSession) -> TokenPair:
    try:
        claims = decode_token(payload.refresh_token)
        if claims.get("type") != REFRESH:
            raise ValueError("not a refresh token")
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    user = UserRepository(db).get(user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    return TokenPair(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
