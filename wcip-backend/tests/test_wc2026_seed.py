"""Tests for the dedicated WC2026 seed ETL."""
from sqlalchemy import func, select

from app.db.base import SessionLocal
from app.models.match_result import QualifiedTeam
from app.models.player import Coach, Player
from app.models.team import EloHistory, Team
from etl.world_cup_2026.ingest import normalize_seed_payload, run_wc2026_seed


def test_wc2026_seed_normalizes_and_upserts_teams_players_coaches(client):
    normalized = normalize_seed_payload({"teams": [{"team": {"name": "Czech Republic", "code": "CZE"}}]})
    assert normalized.teams[0].name == "Czechia"

    payload = {
        "teams": [
            {
                "team": {"name": "Seedland", "code": "SDL"},
                "confederation": "UEFA",
                "elo": 1700,
                "fifa_rank": 20,
                "group_label": "A",
                "pot": 2,
            }
        ],
        "players": [
            {
                "player": {
                    "id": 999001,
                    "name": "Seed Keeper",
                    "age": 28,
                    "nationality": "Seedland",
                },
                "statistics": [
                    {
                        "team": {"name": "Seedland"},
                        "games": {"position": "Goalkeeper", "minutes": 90},
                        "goals": {"total": 0, "assists": 1},
                    }
                ],
                "fitness_score": 0.8,
            }
        ],
        "coaches": [
            {
                "name": "Seed Coach",
                "team_name": "Seedland",
                "nationality": "Seedland",
                "preferred_formation": "4-2-3-1",
                "impact_score": 1.08,
            }
        ],
    }

    first = run_wc2026_seed(payload)

    assert first["players_inserted"] == 1
    assert first["coaches_inserted"] == 1

    db = SessionLocal()
    try:
        team = db.scalar(select(Team).where(Team.name == "Seedland"))
        qualified = db.scalar(select(QualifiedTeam).where(QualifiedTeam.team_name == "Seedland"))
        player = db.scalar(select(Player).where(Player.external_id == "999001"))
        coach = db.scalar(select(Coach).where(Coach.team_name == "Seedland"))

        assert team is not None
        assert team.code == "SDL"
        assert team.elo == 1700
        assert team.fifa_rank == 20
        assert qualified is not None
        assert qualified.group_label == "A"
        assert player is not None
        assert player.team_name == "Seedland"
        assert player.position == "GK"
        assert player.assists == 1
        assert coach is not None
        assert coach.name == "Seed Coach"
        assert coach.preferred_formation == "4-2-3-1"
    finally:
        db.close()

    payload["players"][0]["goals"] = 2
    payload["coaches"][0]["preferred_formation"] = "3-4-2-1"

    second = run_wc2026_seed(payload)

    assert second["players_updated"] == 1
    assert second["coaches_updated"] == 1

    db = SessionLocal()
    try:
        player_count = db.scalar(select(func.count()).select_from(Player).where(Player.external_id == "999001"))
        player = db.scalar(select(Player).where(Player.external_id == "999001"))
        coach = db.scalar(select(Coach).where(Coach.team_name == "Seedland"))

        assert player_count == 1
        assert player.goals == 2
        assert coach.preferred_formation == "3-4-2-1"

        team = db.scalar(select(Team).where(Team.name == "Seedland"))
        if team is not None:
            db.query(EloHistory).filter(EloHistory.team_id == team.id).delete()
        db.query(Player).filter(Player.external_id == "999001").delete()
        db.query(Coach).filter(Coach.team_name == "Seedland").delete()
        db.query(QualifiedTeam).filter(QualifiedTeam.team_name == "Seedland").delete()
        db.query(Team).filter(Team.name == "Seedland").delete()
        db.commit()
    finally:
        db.close()
