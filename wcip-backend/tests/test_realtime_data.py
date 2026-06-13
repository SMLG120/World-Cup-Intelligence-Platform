"""Real-time data pipeline tests."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func, select

from app.db.base import SessionLocal
from app.models.match_result import MatchResult
from app.models.team import EloRatingSnapshot, Team, TeamEloRating
from app.models.user import User, UserRole
from app.services.rating_update_service import update_ratings_after_match
from etl.elo.extract_elo import RawEloRecord, RawEloSnapshot
from etl.elo.load_elo import load_elo_snapshot
from etl.elo.transform_elo import transform_raw_elo_snapshot


def test_elo_snapshot_loader_preserves_history(client):
    raw = RawEloSnapshot(
        source_url="test://elo",
        rating_date=date(2026, 6, 13),
        source_hash="abc123" * 11,
        records=[
            RawEloRecord(team_name="France", rating=2050, rank=1),
            RawEloRecord(team_name="Brazil", rating=1980, rank=2),
            RawEloRecord(team_name="Argentina", rating=1975, rank=3),
            RawEloRecord(team_name="England", rating=1960, rank=4),
            RawEloRecord(team_name="Spain", rating=1955, rank=5),
            RawEloRecord(team_name="Portugal", rating=1930, rank=6),
            RawEloRecord(team_name="Germany", rating=1890, rank=7),
            RawEloRecord(team_name="Netherlands", rating=1880, rank=8),
            RawEloRecord(team_name="Belgium", rating=1860, rank=9),
            RawEloRecord(team_name="Croatia", rating=1840, rank=10),
            RawEloRecord(team_name="Morocco", rating=1810, rank=11),
            RawEloRecord(team_name="Japan", rating=1780, rank=12),
            RawEloRecord(team_name="United States", rating=1760, rank=13),
            RawEloRecord(team_name="Mexico", rating=1755, rank=14),
            RawEloRecord(team_name="Uruguay", rating=1750, rank=15),
            RawEloRecord(team_name="Switzerland", rating=1740, rank=16),
            RawEloRecord(team_name="Senegal", rating=1730, rank=17),
            RawEloRecord(team_name="Canada", rating=1650, rank=18),
            RawEloRecord(team_name="Australia", rating=1640, rank=19),
            RawEloRecord(team_name="New Zealand", rating=1500, rank=20),
        ],
        http_status=200,
    )

    result = load_elo_snapshot(transform_raw_elo_snapshot(raw))

    assert result["entries"] == 20
    response = client.get("/api/v1/ratings/elo/latest?limit=3")
    assert response.status_code == 200
    payload = response.json()
    assert payload["data_version"] == result["data_version"]
    assert len(payload["entries"]) == 3


def test_rating_update_after_match_is_idempotent(client):
    with SessionLocal() as db:
        for name, code, elo in (("Testland A", "TLA", 1500), ("Testland B", "TLB", 1500)):
            team = db.scalar(select(Team).where(Team.name == name))
            if not team:
                db.add(Team(name=name, code=code, confederation="TEST", elo=elo, fifa_rank=100))
        db.commit()
        match = MatchResult(
            match_date=date(2026, 6, 13),
            home_team="Testland A",
            away_team="Testland B",
            home_goals=2,
            away_goals=1,
            tournament="FIFA World Cup",
            neutral=True,
            outcome=2,
            data_source="test",
        )
        db.add(match)
        db.commit()
        match_id = match.id

    first = update_ratings_after_match(match_id)
    second = update_ratings_after_match(match_id)

    assert first.status == "updated"
    assert second.status == "already_processed"
    with SessionLocal() as db:
        count = db.scalar(
            select(func.count()).select_from(EloRatingSnapshot).where(EloRatingSnapshot.snapshot_id == first.snapshot_id)
        )
        entries = db.scalars(
            select(TeamEloRating).join(EloRatingSnapshot).where(EloRatingSnapshot.snapshot_id == first.snapshot_id)
        ).all()
    assert count == 1
    assert len(entries) == 2


def test_data_freshness_endpoint(client):
    response = client.get("/api/v1/data/freshness")
    assert response.status_code == 200
    payload = response.json()
    assert "data_snapshot_version" in payload
    assert "source_status" in payload


def test_admin_refresh_requires_admin(client, auth_headers, monkeypatch):
    user_response = client.post("/api/v1/admin/data/refresh-all", headers=auth_headers)
    assert user_response.status_code == 403
    retrain_user_response = client.post("/api/v1/admin/ml/retrain-if-needed", headers=auth_headers, json={})
    assert retrain_user_response.status_code == 403

    monkeypatch.setattr("app.api.v1.admin_data.refresh_all_data", lambda: {"status": "ok"})
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "tester@example.com"))
        user.role = UserRole.admin
        db.commit()

    admin_response = client.post("/api/v1/admin/data/refresh-all", headers=auth_headers)
    assert admin_response.status_code == 200
    assert admin_response.json()["status"] == "ok"

    retrain_admin_response = client.post(
        "/api/v1/admin/ml/retrain-if-needed",
        headers=auth_headers,
        json={"material_elo_changes": 10, "apply": True},
    )
    assert retrain_admin_response.status_code == 200
    assert retrain_admin_response.json()["action"] == "recalibration"
