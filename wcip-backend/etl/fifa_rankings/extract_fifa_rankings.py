"""Extract official FIFA men's ranking snapshots."""
from __future__ import annotations

from etl.extract.fifa_rankings import RankingSnapshot, fetch_fifa_ranking_snapshot

__all__ = ["RankingSnapshot", "fetch_fifa_ranking_snapshot"]
