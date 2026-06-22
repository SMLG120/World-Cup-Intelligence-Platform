"""Config normalization tests."""
from app.core.config import Settings


def test_postgres_scheme_normalized_to_postgresql():
    s = Settings(DATABASE_URL="postgres://user:pass@host:5432/db")
    assert s.DATABASE_URL == "postgresql://user:pass@host:5432/db"


def test_postgresql_scheme_left_unchanged():
    s = Settings(DATABASE_URL="postgresql://user:pass@host:5432/db")
    assert s.DATABASE_URL == "postgresql://user:pass@host:5432/db"


def test_sqlite_url_left_unchanged():
    s = Settings(DATABASE_URL="sqlite:///./wcip.db")
    assert s.DATABASE_URL == "sqlite:///./wcip.db"
    assert s.is_sqlite is True
