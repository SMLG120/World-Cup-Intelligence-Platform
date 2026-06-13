"""Security primitives: password hashing and JWT tokens."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
import jwt

from app.core.config import settings

ACCESS = "access"
REFRESH = "refresh"

# bcrypt operates on at most 72 bytes; truncate defensively (matches bcrypt's
# own behaviour in older versions and avoids ValueError on bcrypt>=4).
_MAX_BCRYPT_BYTES = 72


def _prepare(password: str) -> bytes:
    return password.encode("utf-8")[:_MAX_BCRYPT_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _create_token(subject: str, token_type: str, expires_delta: timedelta,
                  extra: Optional[dict] = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    if extra:
        payload.update(extra)
    secret = _token_secret(token_type)
    return jwt.encode(payload, secret, algorithm=settings.ALGORITHM)


def _token_secret(token_type: str) -> str:
    if token_type == REFRESH and settings.REFRESH_SECRET_KEY:
        return settings.REFRESH_SECRET_KEY
    return settings.SECRET_KEY


def create_access_token(subject: str, role: str = "user") -> str:
    return _create_token(
        subject, ACCESS,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra={"role": role},
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject, REFRESH,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict:
    """Decode and validate a JWT. Raises jwt exceptions on failure."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.PyJWTError:
        if not settings.REFRESH_SECRET_KEY or settings.REFRESH_SECRET_KEY == settings.SECRET_KEY:
            raise
        return jwt.decode(
            token,
            settings.REFRESH_SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
