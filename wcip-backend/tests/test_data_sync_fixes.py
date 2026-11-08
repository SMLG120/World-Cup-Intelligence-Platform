"""Regression tests for the Nov 2026 data-sync, prediction and cache fixes.

No network access: providers are monkeypatched.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest


# ---------------------------------------------------------------------------
# HTTP retry helper
# ---------------------------------------------------------------------------

def _response(status: int, text: str = "ok", headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, text=text, headers=headers, request=httpx.Request("GET", "https://x.test"))


def test_get_with_retries_retries_transient_status_then_succeeds(monkeypatch):
    from etl.extract import http

    calls = iter([_response(503), _response(429, headers={"Retry-After": "2"}), _response(200, "done")])
    monkeypatch.setattr(http.httpx, "get", lambda *a, **k: next(calls))
    sleeps: list[float] = []

    response = http.get_with_retries("https://x.test", sleep=sleeps.append)

    assert response.text == "done"
    assert sleeps == [1.0, 2.0]  # exponential backoff, then Retry-After honoured


def test_get_with_retries_does_not_retry_client_errors(monkeypatch):
    from etl.extract import http

    calls = []
    monkeypatch.setattr(http.httpx, "get", lambda *a, **k: calls.append(1) or _response(404))

    with pytest.raises(httpx.HTTPStatusError):
        http.get_with_retries("https://x.test", sleep=lambda _: None)
    assert len(calls) == 1


def test_get_with_retries_raises_after_repeated_timeouts(monkeypatch):
    from etl.extract import http

    def boom(*a, **k):
        raise httpx.ReadTimeout("slow")

    monkeypatch.setattr(http.httpx, "get", boom)
    with pytest.raises(httpx.ReadTimeout):
        http.get_with_retries("https://x.test", attempts=3, sleep=lambda _: None)


# ---------------------------------------------------------------------------
# Elo ingestion
# ---------------------------------------------------------------------------

CODED_TSV = "1\t1\tES\t2287\t1\t2287\n2\t2\tAR\t2175\t1\t2200\n244\t244\tAS\t370\t200\t500\n"


def test_elo_tsv_current_coded_layout_is_parsed_with_code_map():
    from etl.elo.extract_elo import _looks_like_coded_tsv, _parse_tsv

    assert _looks_like_coded_tsv(CODED_TSV)
    rows = _parse_tsv(CODED_TSV, code_map={"ES": "Spain", "AR": "Argentina", "AS": "American Samoa"})

    assert [(r.team_name, r.rating, r.rank) for r in rows] == [
        ("Spain", 2287.0, 1),
        ("Argentina", 2175.0, 2),
        ("American Samoa", 370.0, 244),
    ]


def test_elo_legacy_named_layout_still_parses():
    from etl.elo.extract_elo import _parse_tsv

    rows = _parse_tsv("1\tSpain\t2100\n2\tBrazil\t2000\n")
    assert [(r.team_name, r.rating) for r in rows] == [("Spain", 2100.0), ("Brazil", 2000.0)]


def test_elo_network_failure_raises_instead_of_storing_embedded_fallback(monkeypatch, tmp_path):
    from etl.elo import extract_elo

    monkeypatch.setattr(extract_elo, "_CACHE", tmp_path / "elo_snapshot.json")

    def unavailable(*a, **k):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(extract_elo, "get_with_retries", unavailable)

    with pytest.raises(extract_elo.EloSourceUnavailable):
        extract_elo.fetch_latest_elo_snapshot(force_refresh=True, allow_network=True)
    assert not (tmp_path / "elo_snapshot.json").exists()


def test_elo_truncated_source_is_rejected(monkeypatch, tmp_path):
    from etl.elo import extract_elo

    monkeypatch.setattr(extract_elo, "_CACHE", tmp_path / "elo_snapshot.json")
    monkeypatch.setattr(extract_elo, "get_with_retries", lambda url, **k: _response(200, CODED_TSV))
    monkeypatch.setattr(extract_elo, "_fetch_team_code_map", lambda: {"ES": "Spain", "AR": "Argentina"})

    with pytest.raises(extract_elo.EloSourceUnavailable, match="parsed 2 rows"):
        extract_elo.fetch_latest_elo_snapshot(force_refresh=True, allow_network=True)


def test_elo_offline_mode_still_uses_embedded_snapshot_without_caching(monkeypatch, tmp_path):
    from etl.elo import extract_elo

    monkeypatch.setattr(extract_elo, "_CACHE", tmp_path / "elo_snapshot.json")
    snapshot = extract_elo.fetch_latest_elo_snapshot(force_refresh=True, allow_network=False)

    assert snapshot.source_url.startswith("embedded://")
    assert not (tmp_path / "elo_snapshot.json").exists()


def test_cached_embedded_elo_snapshot_is_ignored(monkeypatch, tmp_path):
    from etl.elo import extract_elo

    cache_file = tmp_path / "elo_snapshot.json"
    cache_file.write_text(json.dumps({
        "source_url": "embedded://etl.extract.elo_ratings._ELO_FALLBACK",
        "rating_date": "2026-01-01", "source_hash": "x", "records": [],
    }))
    monkeypatch.setattr(extract_elo, "_CACHE", cache_file)
    monkeypatch.setattr(extract_elo, "get_with_retries", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("down")))

    with pytest.raises(extract_elo.EloSourceUnavailable):
        extract_elo.fetch_latest_elo_snapshot(force_refresh=False, allow_network=True)


def test_elo_validation_accepts_real_minnow_ratings():
    from etl.elo.transform_elo import EloSnapshot  # noqa: F401  (import check)
    from etl.elo.validate_elo import validate_elo_snapshot

    records = [SimpleNamespace(team_name=f"T{i}", rating=370.0 + i, rank=i + 1) for i in range(30)]
    report = validate_elo_snapshot(SimpleNamespace(snapshot_id="s", records=records))
    assert report.ok, report.errors

    bad = records + [SimpleNamespace(team_name="Broken", rating=0.0, rank=31)]
    assert not validate_elo_snapshot(SimpleNamespace(snapshot_id="s", records=bad)).ok


# ---------------------------------------------------------------------------
# Team-name normalisation and match-result loading
# ---------------------------------------------------------------------------

def test_renamed_teams_map_to_existing_canonical_names():
    from etl.transform.normalize import canonical

    assert canonical("China") == "China PR"
    assert canonical("China PR") == "China PR"
    assert canonical("Canton Ticino") == "Ticino"


def _match(day: date, home: str, away: str):
    from etl.validation.schema import ValidatedMatch

    return ValidatedMatch(
        match_date=day, home_team=home, away_team=away, home_goals=1, away_goals=0,
        tournament="Friendly", city=None, country=None, neutral=False, outcome=2,
    )


def test_match_loader_is_idempotent(client):
    from etl.load.db_loader import load_match_results

    rows = [_match(date(1990, 1, d), "Loader A", "Loader B") for d in range(1, 4)]
    assert load_match_results(iter(rows)) == 3
    assert load_match_results(iter(rows + rows)) == 0  # stored + in-file duplicates skipped


def test_backfill_guard_blocks_rename_duplicates(client, monkeypatch):
    from etl.load import db_loader

    seed = [_match(date(1991, 2, 1) + timedelta(days=i), "Guard Old", f"Opp {i}") for i in range(10)]
    db_loader.load_match_results(iter(seed))
    monkeypatch.setattr(db_loader, "BACKFILL_GUARD_MIN_EXISTING", 5)
    monkeypatch.setattr(db_loader, "BACKFILL_GUARD_MAX_OLD_INSERTS", 3)

    renamed = [_match(m.match_date, "Guard New", m.away_team) for m in seed]
    with pytest.raises(db_loader.SuspiciousBackfillError, match="Guard New"):
        db_loader.load_match_results(iter(renamed), guard_backfill=True)

    # Recent matches are normal sync traffic and are not blocked.
    recent = [_match(date.today() - timedelta(days=2), "Guard Old", "Recent Opp")]
    assert db_loader.load_match_results(iter(recent), guard_backfill=True) == 1


# ---------------------------------------------------------------------------
# Elo feature lookup with partial (per-match) snapshots
# ---------------------------------------------------------------------------

def _add_elo_snapshot(db, snapshot_id: str, day: date, ratings: dict[str, float], *, current: bool):
    from app.models.team import EloRatingSnapshot, TeamEloRating

    snap = EloRatingSnapshot(
        snapshot_id=snapshot_id, rating_date=day, source_url="test", source_hash=snapshot_id,
        team_count=len(ratings), is_current=current, data_version=snapshot_id,
    )
    db.add(snap)
    db.flush()
    for name, rating in ratings.items():
        db.add(TeamEloRating(
            snapshot_id=snap.id, team_name=name, rating=rating, rating_date=day,
            source_url="test", data_version=snapshot_id,
        ))


def test_team_elo_survives_partial_match_snapshots(client):
    from app.db.base import SessionLocal
    from ml.features import _get_team_elo

    with SessionLocal() as db:
        _add_elo_snapshot(db, "full-2020-01-01", date(2020, 1, 1), {"Elo Alpha": 1900.0, "Elo Beta": 1700.0}, current=False)
        # A later live-match snapshot that only contains Beta and Gamma.
        _add_elo_snapshot(db, "match-2020-02-01", date(2020, 2, 1), {"Elo Beta": 1720.0, "Elo Gamma": 1500.0}, current=False)
        db.commit()

    assert _get_team_elo("Elo Alpha", date(2020, 3, 1)) == 1900.0  # was 1500 before the fix
    assert _get_team_elo("Elo Beta", date(2020, 3, 1)) == 1720.0


def test_historical_elo_lookup_excludes_same_day_snapshot(client):
    from app.db.base import SessionLocal
    from ml.features import _get_team_elo

    with SessionLocal() as db:
        _add_elo_snapshot(db, "full-2019-05-01", date(2019, 5, 1), {"Leak Team": 1600.0}, current=False)
        _add_elo_snapshot(db, "match-2019-06-01", date(2019, 6, 1), {"Leak Team": 1650.0}, current=False)
        db.commit()

    # A prediction for a match on 2019-06-01 must not see that day's post-match rating.
    assert _get_team_elo("Leak Team", date(2019, 6, 1)) == 1600.0
    assert _get_team_elo("Leak Team", date(2019, 6, 2)) == 1650.0


# ---------------------------------------------------------------------------
# CatBoost inference
# ---------------------------------------------------------------------------

def test_feature_count_zero_falls_back_to_feature_names():
    from ml.predict import _model_feature_count

    fake = SimpleNamespace(n_features_in_=0, feature_names_=[f"f{i}" for i in range(33)])
    assert _model_feature_count(fake) == 33
    assert _model_feature_count(SimpleNamespace()) is None


def test_shipped_catboost_model_produces_predictions():
    import numpy as np

    from ml.features import FEATURE_NAMES, FeatureVector
    from ml.predict import _load_model, predict_with_model

    if _load_model("catboost") is None:
        pytest.skip("catboost artifact not present")
    fv = FeatureVector(
        home_team="A", away_team="B", match_date=date(2026, 7, 1),
        features=np.zeros(len(FEATURE_NAMES)),
    )
    pred = predict_with_model("catboost", fv)
    assert pred is not None
    assert abs(sum(pred.values()) - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# FIFA conditional check
# ---------------------------------------------------------------------------

def test_fifa_monitor_skips_payload_when_release_unchanged(monkeypatch):
    from etl.extract.fifa_rankings import LatestRankingInfo
    from etl.monitoring import ranking_monitor

    monkeypatch.setattr(ranking_monitor, "_get_current_snapshot", lambda: {
        "ranking_id": "FRS_TEST", "ranking_date": date(2026, 10, 7), "entries": {},
    })
    monkeypatch.setattr(ranking_monitor, "fetch_latest_ranking_info", lambda: LatestRankingInfo(
        ranking_id="FRS_TEST", published_at=None, next_update_at=datetime(2026, 11, 18, tzinfo=timezone.utc),
    ))

    def must_not_download(**kwargs):
        raise AssertionError("full ranking payload should not be fetched")

    monkeypatch.setattr(ranking_monitor, "fetch_fifa_ranking_snapshot", must_not_download)

    result = ranking_monitor.check_fifa_ranking_update(force_refresh=True)
    assert result["not_modified"] is True and result["changed"] is False


# ---------------------------------------------------------------------------
# Prediction cache
# ---------------------------------------------------------------------------

def test_prediction_cache_reuses_result_until_data_version_changes(monkeypatch):
    from app.services import prediction_cache

    versions = iter(["v1", "v1", "v2"])
    monkeypatch.setattr(prediction_cache, "data_version", lambda: next(versions))
    calls = []

    def compute():
        calls.append(1)
        return {"n": len(calls)}

    payload = {"home": "Cache A", "away": "Cache B", "match_date": "2030-01-01"}
    assert prediction_cache.cached_prediction("test", payload, compute) == {"n": 1}
    assert prediction_cache.cached_prediction("test", payload, compute) == {"n": 1}
    assert prediction_cache.cached_prediction("test", payload, compute) == {"n": 2}


def test_predict_endpoint_serves_identical_payload_from_cache(client):
    body = {"home_team": "Mexico", "away_team": "Czechia", "include_shap": False}
    first = client.post("/api/v1/match/predict", json=body)
    second = client.post("/api/v1/match/predict", json=body)

    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()


def test_ml_predict_error_does_not_leak_exception_text(client, monkeypatch):
    import ml.ensemble

    def explode(**kwargs):
        raise RuntimeError("postgresql://user:secret@internal-host/db")

    monkeypatch.setattr(ml.ensemble, "predict_hybrid", explode)
    response = client.post("/api/v1/ml/predict", json={"home_team": "Leakland", "away_team": "Brazil"})

    assert response.status_code == 500
    assert "secret" not in response.text and "internal-host" not in response.text


# ---------------------------------------------------------------------------
# Memory cache bound, readiness, config
# ---------------------------------------------------------------------------

def test_memory_cache_is_bounded(monkeypatch):
    from app.core.cache import _MemoryCache

    monkeypatch.setattr(_MemoryCache, "MAX_ENTRIES", 100)
    mem = _MemoryCache()
    for i in range(1_000):
        mem.setex(f"rl:client-{i}:1", 60, "1")
    assert len(mem._store) <= 100


def test_ready_endpoint_reports_booleans_only(client):
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"database": True, "models": True}}


def test_production_refuses_sqlite_database_url():
    from app.core.config import Settings

    with pytest.raises(ValueError, match="DATABASE_URL"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 48,
            JWT_REFRESH_SECRET_KEY="b" * 48,
            DATABASE_URL="sqlite:///./wcip.db",
        )
