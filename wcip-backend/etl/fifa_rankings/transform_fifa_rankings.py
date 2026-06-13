"""Transform layer for FIFA rankings.

FIFA ranking normalization currently happens inside
``etl.extract.fifa_rankings`` because the official payload includes localized
country names and rank metadata. This module provides an explicit package
boundary for future transformations without creating a second code path.
"""
from __future__ import annotations

from etl.extract.fifa_rankings import RankingSnapshot


def transform_fifa_ranking_snapshot(snapshot: RankingSnapshot) -> RankingSnapshot:
    return snapshot
