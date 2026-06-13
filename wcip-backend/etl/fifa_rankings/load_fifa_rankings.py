"""Load official FIFA ranking snapshots through the canonical loader."""
from __future__ import annotations

from typing import Any

from etl.load.ranking_loader import (
    load_fifa_ranking_snapshot,
    load_latest_fifa_ranking_snapshot,
)


def load_latest_fifa_rankings(force_refresh: bool = False) -> dict[str, Any]:
    return load_latest_fifa_ranking_snapshot(force_refresh=force_refresh)


__all__ = ["load_fifa_ranking_snapshot", "load_latest_fifa_rankings"]
