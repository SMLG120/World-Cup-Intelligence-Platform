"""Shared test fixtures."""
import os
import tempfile

import pytest

# Configure the app for testing BEFORE importing it.
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"
os.environ["CELERY_TASK_ALWAYS_EAGER"] = "true"
os.environ["SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["RATE_LIMIT_PER_MINUTE"] = "100000"  # don't throttle the suite

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def auth_headers(client):
    email = "tester@example.com"
    client.post("/api/v1/auth/register",
                json={"email": email, "password": "password123",
                      "full_name": "Tester"})
    tok = client.post("/api/v1/auth/login",
                      data={"username": email, "password": "password123"}).json()
    return {"Authorization": f"Bearer {tok['access_token']}"}


def pytest_sessionfinish(session, exitstatus):
    try:
        os.unlink(_tmp_db.name)
    except OSError:
        pass
