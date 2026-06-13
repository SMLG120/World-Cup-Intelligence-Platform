"""Player intelligence ingestion helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_player_profile(player: Any) -> str:
    from etl.players.profiles import build_player_profile as _build_player_profile

    return _build_player_profile(player)


def import_world_cup_players_csv(
    source_path: str | Path,
    *,
    source_name: str = "manual_player_csv",
    source_version: str | None = None,
    source_url: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    from etl.players.csv_import import import_world_cup_players_csv as _import_world_cup_players_csv

    return _import_world_cup_players_csv(
        source_path,
        source_name=source_name,
        source_version=source_version,
        source_url=source_url,
        notes=notes,
    )

__all__ = ["build_player_profile", "import_world_cup_players_csv"]
