"""FIFA ranking ingestion and point-in-time feature tests."""
from datetime import date, datetime, timezone

from etl.extract.fifa_rankings import RankingEntry, RankingSnapshot
from etl.load.ranking_loader import load_fifa_ranking_snapshot
from ml.features import _get_team_elo, _get_team_fifa_rank, build_feature_vector


def _snapshot(ranking_id: str, ranking_date: date, entries: list[RankingEntry]) -> RankingSnapshot:
    return RankingSnapshot(
        ranking_id=ranking_id,
        ranking_date=ranking_date,
        published_at=datetime.combine(ranking_date, datetime.min.time(), tzinfo=timezone.utc),
        next_update_at=None,
        source_url=f"https://inside.fifa.com/fifa-world-ranking/men?dateId={ranking_id}",
        source_hash=f"test-{ranking_id}",
        entries=entries,
    )


def test_versioned_fifa_ranking_snapshot_is_loaded_and_exposed(client):
    result = load_fifa_ranking_snapshot(
        _snapshot(
            "test-ranking-20260401",
            date(2026, 4, 1),
            [
                RankingEntry(team_name="France", team_code="FRA", rank=1, previous_rank=3, points=1877.32),
                RankingEntry(team_name="Brazil", team_code="BRA", rank=6, previous_rank=5, points=1776.03),
            ],
        )
    )

    assert result["snapshot_inserted"] in {True, False}
    assert result["entries"] == 2

    response = client.get("/api/v1/rankings/fifa/latest?limit=2")
    assert response.status_code == 200
    body = response.json()
    assert body["ranking_id"] == "test-ranking-20260401"
    assert body["entries"][0]["team_name"] == "France"
    assert body["entries"][0]["rank"] == 1


def test_features_use_historical_ranking_snapshot_without_future_leakage(client):
    load_fifa_ranking_snapshot(
        _snapshot(
            "test-ranking-20240101",
            date(2024, 1, 1),
            [
                RankingEntry(team_name="Brazil", team_code="BRA", rank=1, previous_rank=1),
                RankingEntry(team_name="France", team_code="FRA", rank=2, previous_rank=2),
            ],
        )
    )
    load_fifa_ranking_snapshot(
        _snapshot(
            "test-ranking-20260401",
            date(2026, 4, 1),
            [
                RankingEntry(team_name="France", team_code="FRA", rank=1, previous_rank=3),
                RankingEntry(team_name="Brazil", team_code="BRA", rank=6, previous_rank=5),
            ],
        )
    )

    assert _get_team_fifa_rank("Brazil", date(2025, 1, 1)) == 1
    assert _get_team_fifa_rank("Brazil", date(2026, 4, 2)) == 6

    fv = build_feature_vector("Brazil", "France", date(2025, 1, 1))
    rank_diff = float(fv.features[1])
    assert rank_diff == 1.0


def test_missing_historical_rank_and_elo_use_neutral_defaults(client):
    load_fifa_ranking_snapshot(
        _snapshot(
            "test-ranking-20260401",
            date(2026, 4, 1),
            [
                RankingEntry(team_name="France", team_code="FRA", rank=1),
                RankingEntry(team_name="Brazil", team_code="BRA", rank=6),
            ],
        )
    )

    assert _get_team_fifa_rank("Brazil", date(2001, 1, 1)) == 100
    assert _get_team_elo("Brazil", date(2001, 1, 1)) == 1500.0
