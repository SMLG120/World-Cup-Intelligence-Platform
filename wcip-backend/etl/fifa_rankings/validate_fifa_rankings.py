"""Validation wrapper for official FIFA ranking snapshots."""
from __future__ import annotations

from etl.extract.fifa_rankings import RankingSnapshot, validate_ranking_snapshot

__all__ = ["RankingSnapshot", "validate_ranking_snapshot"]
