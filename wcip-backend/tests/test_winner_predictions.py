from pathlib import Path

from app.db.base import SessionLocal
from app.models.player import Player
from app.services.probabilities import normalize_probabilities, validate_probability_distribution
from scripts.validate_elo_csv import MANDATORY_TOP_ROWS, validate_rows
from etl.player_ratings import import_player_ratings_csv
from ml.features import FEATURE_NAMES, build_feature_vector


def test_probability_helpers_normalize_and_validate_distribution():
    probs = normalize_probabilities({"A": 2.0, "B": 1.0, "C": -5.0})
    assert round(sum(probs.values()), 8) == 1.0
    assert probs["A"] > probs["B"] > probs["C"]
    assert validate_probability_distribution(probs)
    assert not validate_probability_distribution({"A": 1.2, "B": -0.2})


def test_winner_predictions_endpoint_returns_normalized_rows(client):
    response = client.get("/api/v1/world-cup/2026/winner-predictions?runs=100&seed=7")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 48
    assert rows[0]["rank"] == 1
    assert "team_name" in rows[0]
    assert "champion_probability" in rows[0]
    assert "ml_probability" in rows[0]
    assert "statistical_probability" in rows[0]
    assert "ensemble_probability" in rows[0]
    assert "elo_rating_used" in rows[0]
    assert "elo_rank_used" in rows[0]
    assert "elo_source" in rows[0]
    assert "elo_source_date" in rows[0]
    assert "elo_snapshot_version" in rows[0]
    total = sum(row["champion_probability"] for row in rows)
    assert 0.999 <= total <= 1.001
    assert all(0 <= row["champion_probability"] <= 1 for row in rows)
    assert all(0 <= row["ensemble_probability"] <= 1 for row in rows)


def test_elo_csv_top_six_rows_validate_without_full_extract():
    rows = [
        {
            "rank": str(rank),
            "team": team,
            "rating": str(rating),
            "average_rank": "1",
            "average_rating": str(rating),
            "one_year_change_rank": "0",
            "one_year_change_rating": "0",
            "matches_total": "1",
            "matches_home": "0",
            "matches_away": "0",
            "matches_neutral": "1",
            "wins": "1",
            "losses": "0",
            "draws": "0",
            "goals_for": "1",
            "goals_against": "0",
            "source_name": "World Football Elo Ratings PDF",
            "source_date": "2026-06-21",
        }
        for team, rank, rating in MANDATORY_TOP_ROWS
    ]
    result = validate_rows(rows, require_full_extract=False, check_db_teams=False)
    assert result["mandatory_top_rows"] == 6


def test_winner_predictions_default_seed_uses_entropy(client):
    first = client.get("/api/v1/world-cup/2026/winner-predictions?runs=100")
    second = client.get("/api/v1/world-cup/2026/winner-predictions?runs=100")
    assert first.status_code == 200
    assert second.status_code == 200
    first_rows = first.json()
    second_rows = second.json()
    assert first_rows[0]["seed"] != second_rows[0]["seed"]
    assert first_rows[0]["deterministic"] is False
    assert second_rows[0]["deterministic"] is False

    seeded_a = client.get("/api/v1/world-cup/2026/winner-predictions?runs=100&seed=7")
    seeded_b = client.get("/api/v1/world-cup/2026/winner-predictions?runs=100&seed=7")
    assert seeded_a.json() == seeded_b.json()


def test_player_rating_csv_import_updates_players_and_history(client, tmp_path: Path):
    csv_path = tmp_path / "ratings.csv"
    csv_path.write_text(
        "\n".join([
            "player_name,team_name,position,club,age,international_caps,international_goals,recent_form_score,injured,suspended,minutes_played,goals,assists,xg,xa,market_value_eur,ea_fc_rating",
            "Example Forward,France,FWD,Paris,26,50,20,0.9,false,false,900,8,4,7.1,3.2,90000000,91",
            "Example Keeper,France,GK,Lyon,30,40,0,0.8,false,false,900,0,0,0,0,25000000,86",
        ]),
        encoding="utf-8",
    )

    result = import_player_ratings_csv(csv_path, source_name="test_csv", source_version="test-v1")
    assert result["valid_rows"] == 2
    assert result["skipped_rows"] == 0

    db = SessionLocal()
    try:
        player = db.query(Player).filter_by(team_name="France", name="Example Forward").one()
        assert player.ea_fc_rating == 91
        assert player.player_rating == 91
        assert player.player_rating_version == "test-v1"
    finally:
        db.close()


def test_player_rating_features_are_included_and_directional(client):
    db = SessionLocal()
    try:
        db.add(Player(name="High Rated", team_name="France", position="FWD", player_rating=92, recent_form_score=0.9))
        db.add(Player(name="Low Rated", team_name="Brazil", position="FWD", player_rating=70, recent_form_score=0.5))
        db.commit()
    finally:
        db.close()

    fv = build_feature_vector("France", "Brazil")
    idx = FEATURE_NAMES.index("weighted_player_strength_diff")
    assert fv.features.shape[0] == len(FEATURE_NAMES)
    assert fv.features[idx] > 0
