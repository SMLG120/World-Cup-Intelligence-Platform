"""Reusable FastAPI dependencies."""
from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.security import ACCESS, decode_token
from app.db.base import get_db
from app.models.user import User, UserRole
from app.repositories.repos import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login",
                                     auto_error=True)

DbSession = Annotated[Session, Depends(get_db)]
Token = Annotated[str, Depends(oauth2_scheme)]

_CRED_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(token: Token, db: DbSession) -> User:
    try:
        payload = decode_token(token)
        if payload.get("type") != ACCESS:
            raise _CRED_EXC
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _CRED_EXC
    user = UserRepository(db).get(user_id)
    if user is None or not user.is_active:
        raise _CRED_EXC
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Admin privileges required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]
