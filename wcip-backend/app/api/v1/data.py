"""Read-only data freshness API."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.deps import DbSession
from app.services.data_refresh_service import get_data_freshness_from_db

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/freshness")
def data_freshness(db: DbSession) -> dict[str, Any]:
    return get_data_freshness_from_db(db)
