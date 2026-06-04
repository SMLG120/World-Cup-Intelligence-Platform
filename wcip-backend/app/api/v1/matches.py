"""Match & tournament prediction endpoints."""
from __future__ import annotations

import hashlib
import json

from fastapi import APIRouter, HTTPException

from app.core.cache import cache
from app.services import prediction
from app.schemas.domain import (MatchPrediction, MatchRequest,
                                TournamentRequest)

router = APIRouter(tags=["predictions"])


def _hash(payload: dict) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


@router.post("/match/simulate", response_model=MatchPrediction)
def simulate_match(req: MatchRequest):
    key = f"match:{_hash(req.model_dump())}"
    cached = cache.get_json(key)
    if cached is not None:
        return cached
    try:
        result = prediction.predict_match(
            req.home, req.away,
            req.home_modifiers.model_dump(),
            req.away_modifiers.model_dump(),
        )
    except prediction.UnknownTeam as exc:
        raise HTTPException(404, f"Unknown team: {exc}")
    cache.set_json(key, result)
    return result


@router.post("/tournament/simulate")
def simulate_tournament(req: TournamentRequest):
    """Synchronous Monte Carlo for small run counts.

    For large runs the client should POST /simulations (async via Celery).
    """
    from app.core.config import settings
    if req.runs > settings.SYNC_SIM_RUN_THRESHOLD:
        raise HTTPException(
            413,
            f"runs={req.runs} exceeds the synchronous limit "
            f"({settings.SYNC_SIM_RUN_THRESHOLD}). Use POST /simulations "
            "to run this asynchronously.",
        )
    overrides = {k: v.model_dump() for k, v in req.overrides.items()}
    try:
        return prediction.run_monte_carlo(req.edition, req.runs, overrides)
    except prediction.UnknownEdition as exc:
        raise HTTPException(404, str(exc))
