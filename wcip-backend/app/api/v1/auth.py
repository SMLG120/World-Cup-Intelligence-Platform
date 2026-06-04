"""Authentication endpoints."""
from __future__ import annotations

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.deps import CurrentUser, DbSession
from app.core.security import (REFRESH, create_access_token,
                               create_refresh_token, decode_token,
                               hash_password, verify_password)
from app.models.user import User
from app.repositories.repos import UserRepository
from app.schemas.auth import (RefreshRequest, TokenPair, UserCreate, UserOut)

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
def login(db: DbSession,
          form: OAuth2PasswordRequestForm = Depends()) -> TokenPair:
    """OAuth2 password flow. `username` field carries the email."""
    repo = UserRepository(db)
    user = repo.get_by_email(form.username)
    if (user is None or not user.hashed_password
            or not verify_password(form.password, user.hashed_password)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account disabled")
    return TokenPair(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id)),
    )


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
