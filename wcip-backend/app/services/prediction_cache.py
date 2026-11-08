"""Caching and input checks for prediction endpoints.

Predictions are deterministic for a given (teams, date, overrides) and data
state, and cost ~300-500 ms of feature queries + 5-model inference. Results
are cached under a key that embeds a *data version* derived from the stored
snapshots, so the moment the sync job (a separate Render process) loads new
Elo, FIFA, match or model data, every key changes and stale predictions are
never served - no cross-process invalidation needed.

Concurrent identical requests share one computation (single-flight), which
prevents a cache stampede when a popular match is first requested.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from datetime import date
from typing import Any, Callable

from sqlalchemy import func, select

from app.core.cache import cache

logger = logging.getLogger(__name__)

PREDICTION_TTL_SECONDS = 60 * 60
_VERSION_TTL_SECONDS = 30.0

_version_lock = threading.Lock()
_version_value: str | None = None
_version_expires = 0.0

_flight_guard = threading.Lock()
_flights: dict[str, threading.Lock] = {}


def data_version() -> str:
    """Short fingerprint of everything a prediction depends on (memoized 30 s)."""

    global _version_value, _version_expires
    now = time.monotonic()
    if _version_value is not None and now < _version_expires:
        return _version_value
    with _version_lock:
        if _version_value is not None and time.monotonic() < _version_expires:
            return _version_value
        from app.db.base import SessionLocal
        from app.models.match_result import MLModelRecord, MatchResult
        from app.models.player import Player
        from app.models.ranking import FifaRankingSnapshot
        from app.models.team import EloRatingSnapshot

        with SessionLocal() as db:
            parts = [
                db.scalar(select(func.max(EloRatingSnapshot.id))),
                db.scalar(select(func.max(FifaRankingSnapshot.id))),
                db.scalar(select(func.max(MatchResult.id))),
                db.scalar(select(func.max(Player.updated_at))),
                sorted(
                    (r.model_name, r.version, r.ensemble_weight)
                    for r in db.scalars(select(MLModelRecord).where(MLModelRecord.is_active.is_(True)))
                ),
            ]
        _version_value = hashlib.sha256(json.dumps(parts, default=str).encode()).hexdigest()[:12]
        _version_expires = time.monotonic() + _VERSION_TTL_SECONDS
        return _version_value


def cached_prediction(namespace: str, payload: dict[str, Any], compute: Callable[[], Any]) -> Any:
    """Return a cached result for ``payload`` or compute it once."""

    payload = {**payload, "match_date": str(payload.get("match_date") or date.today())}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:20]
    key = f"prediction:{namespace}:{data_version()}:{digest}"

    hit = cache.get_json(key)
    if hit is not None:
        return hit

    with _flight_guard:
        lock = _flights.setdefault(key, threading.Lock())
    with lock:
        hit = cache.get_json(key)  # another request may have filled it meanwhile
        if hit is not None:
            return hit
        result = compute()
        try:
            cache.set_json(key, result, ttl=PREDICTION_TTL_SECONDS)
        except Exception:  # noqa: BLE001 - caching must never fail a request
            logger.warning("Could not cache prediction %s", key, exc_info=True)
    with _flight_guard:
        _flights.pop(key, None)
    return result
