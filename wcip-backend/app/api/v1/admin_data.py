"""Admin-only data refresh endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.core.deps import AdminUser
from app.services.data_refresh_service import (
    refresh_all_data,
    refresh_all_live_football_data,
    refresh_elo_ratings,
    refresh_fifa_rankings,
    refresh_player_availability,
)

router = APIRouter(prefix="/admin/data", tags=["admin-data"])


@router.post("/refresh-elo")
def admin_refresh_elo(_user: AdminUser) -> dict[str, Any]:
    return refresh_elo_ratings()


@router.post("/refresh-fifa-rankings")
def admin_refresh_fifa_rankings(_user: AdminUser) -> dict[str, Any]:
    return refresh_fifa_rankings()


@router.post("/refresh-players")
def admin_refresh_players(_user: AdminUser) -> dict[str, Any]:
    return refresh_player_availability()


@router.post("/refresh-all")
def admin_refresh_all(_user: AdminUser) -> dict[str, Any]:
    return refresh_all_data()


@router.post("/refresh-all-live")
def admin_refresh_all_live(_user: AdminUser) -> dict[str, Any]:
    """Coordinated live data refresh: results → Elo → FIFA → players → cache → retrain check."""
    return refresh_all_live_football_data()


@router.post("/ingest-squad-pdf")
def admin_ingest_squad_pdf(
    _user: AdminUser,
    download: bool = Query(
        default=False,
        description="Download the PDF from FIFA if not already present locally",
    ),
    dry_run: bool = Query(
        default=False,
        description="Parse and validate only; do not write to the database",
    ),
) -> dict[str, Any]:
    """Load the FIFA WC2026 squad PDF into the database.

    Parses all 48 nations' squad lists (~1,248 players and 48 head coaches)
    and upserts the records. Fails with 422 if fewer than 1,000 players are
    parsed, which indicates a likely PDF parsing failure.
    """
    from datetime import datetime, timezone
    from etl.players.load_squad_pdf import load_squad_from_pdf

    started = datetime.now(timezone.utc)
    try:
        result = load_squad_from_pdf(download=download, dry_run=dry_run)
        return {
            "task": "ingest_squad_pdf",
            "status": "ok",
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "result": result,
        }
    except (FileNotFoundError, ValueError) as exc:
        return {
            "task": "ingest_squad_pdf",
            "status": "failed",
            "started_at": started.isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error_code": "squad_pdf_ingest_failed",
            "message": str(exc),
        }
