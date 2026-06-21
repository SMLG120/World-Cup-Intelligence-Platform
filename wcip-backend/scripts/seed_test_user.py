"""Seed the local development/test login user.

Run:
    python -m scripts.seed_test_user
"""
from __future__ import annotations

import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import SessionLocal
from app.db.init_db import create_tables
from app.models.user import User, UserRole

TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testtest"

ALLOWED_ENVIRONMENTS = {"development", "dev", "test", "testing", "local"}


def seed_test_user() -> dict[str, str | bool]:
    environment = settings.ENVIRONMENT.lower()
    if environment not in ALLOWED_ENVIRONMENTS:
        raise RuntimeError(
            "Refusing to seed test user outside development/test environment"
        )

    create_tables()
    db = SessionLocal()
    try:
        user = db.scalar(select(User).where(User.email == TEST_EMAIL))
        if user:
            changed = False
            if not user.hashed_password:
                user.hashed_password = hash_password(TEST_PASSWORD)
                changed = True
            if not user.is_active:
                user.is_active = True
                changed = True
            if changed:
                db.commit()
            return {"email": TEST_EMAIL, "created": False, "updated": changed}

        db.add(
            User(
                email=TEST_EMAIL,
                full_name="Test User",
                hashed_password=hash_password(TEST_PASSWORD),
                role=UserRole.user,
                is_active=True,
            )
        )
        db.commit()
        return {"email": TEST_EMAIL, "created": True, "updated": False}
    finally:
        db.close()


def main() -> int:
    try:
        result = seed_test_user()
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 2
    action = "created" if result["created"] else ("updated" if result["updated"] else "already present")
    print(f"Seed user {TEST_EMAIL}: {action}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
