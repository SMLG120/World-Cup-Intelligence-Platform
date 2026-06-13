"""Admin-only data refresh endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core.deps import AdminUser
from app.services.data_refresh_service import (
    refresh_all_data,
    refresh_elo_ratings,
    refresh_fifa_rankings,
)

router = APIRouter(prefix="/admin/data", tags=["admin-data"])


@router.post("/refresh-elo")
def admin_refresh_elo(_user: AdminUser) -> dict[str, Any]:
    return refresh_elo_ratings()


@router.post("/refresh-fifa-rankings")
def admin_refresh_fifa_rankings(_user: AdminUser) -> dict[str, Any]:
    return refresh_fifa_rankings()


@router.post("/refresh-all")
def admin_refresh_all(_user: AdminUser) -> dict[str, Any]:
    return refresh_all_data()
