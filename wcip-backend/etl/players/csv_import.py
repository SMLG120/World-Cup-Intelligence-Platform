"""CSV player intelligence import wrapper.

Use this with official, licensed, public, or manually maintained CSV files.
The project intentionally avoids scraping restricted player-data websites.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from etl.player_ratings.csv_import import import_player_ratings_csv


def import_world_cup_players_csv(
    source_path: str | Path,
    *,
    source_name: str = "manual_player_csv",
    source_version: str | None = None,
    source_url: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    return import_player_ratings_csv(
        source_path,
        source_name=source_name,
        source_version=source_version,
        source_url=source_url,
        notes=notes,
    )
