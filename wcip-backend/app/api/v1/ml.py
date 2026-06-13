"""ML prediction, training, and explainability API endpoints."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.deps import AdminUser, CurrentUser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ml", tags=["ml"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class TeamOverrides(BaseModel):
    elo: Optional[float] = None
    fifa_rank: Optional[int] = Field(None, ge=1, le=250)
    form: Optional[float] = Field(None, ge=0, le=3)
    injury_burden: Optional[float] = Field(None, ge=0, le=1)
    coach_impact: Optional[float] = Field(None, ge=0, le=2)
    chemistry: Optional[float] = Field(None, ge=0, le=2)
    fitness_score: Optional[float] = Field(None, ge=0, le=1)


class MLPredictRequest(BaseModel):
    home_team: str
    away_team: str
    match_date: Optional[date] = None
    home_overrides: Optional[TeamOverrides] = None
    away_overrides: Optional[TeamOverrides] = None
    include_shap: bool = True


class MLTrainRequest(BaseModel):
    model: str = Field("all", description="Model name or 'all'")
    full_refresh: bool = False


class MLRetrainRequest(BaseModel):
    model: str = "all"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/predict")
def ml_predict(req: MLPredictRequest) -> Dict[str, Any]:
    """Generate a full hybrid prediction: statistical + ML + ensemble.

    Returns probabilities from all three layers plus SHAP explanations.
    """
    from ml.ensemble import predict_hybrid
    from ml.features import build_feature_vector
    from etl.transform.normalize import canonical

    home = canonical(req.home_team)
    away = canonical(req.away_team)

    if home == away:
        raise HTTPException(400, "home_team and away_team must be different")

    ho = req.home_overrides.model_dump(exclude_none=True) if req.home_overrides else {}
    ao = req.away_overrides.model_dump(exclude_none=True) if req.away_overrides else {}

    try:
        result = predict_hybrid(
            home_team=home,
            away_team=away,
            match_date=req.match_date,
            home_overrides=ho if ho else None,
            away_overrides=ao if ao else None,
            include_shap=req.include_shap,
        )
        return result.to_dict()
    except Exception as e:
        logger.exception("ML predict failed: %s", e)
        raise HTTPException(500, f"Prediction failed: {e}")


@router.post("/train")
def ml_train(req: MLTrainRequest, background_tasks: BackgroundTasks,
             _user: AdminUser):
    """Trigger model training (admin only). Runs asynchronously."""
    valid_models = {"all", "logistic", "random_forest", "xgboost", "lightgbm", "catboost"}
    if req.model not in valid_models:
        raise HTTPException(400, f"model must be one of {valid_models}")

    background_tasks.add_task(_do_train, req.model, req.full_refresh)
    return {"status": "training_started", "model": req.model, "full_refresh": req.full_refresh}


def _do_train(model: str, full_refresh: bool) -> None:
    try:
        from ml.train import run_training
        results = run_training(model_filter=model, full_refresh=full_refresh)
        logger.info("Training complete: %s", results)
    except Exception as e:
        logger.error("Background training failed: %s", e)


@router.post("/retrain")
def ml_retrain(req: MLRetrainRequest, background_tasks: BackgroundTasks,
               _user: AdminUser):
    """Retrain models incrementally on latest data."""
    background_tasks.add_task(_do_retrain, req.model)
    return {"status": "retrain_started", "model": req.model}


def _do_retrain(model: str) -> None:
    try:
        from ml.retrain import run_retrain
        run_retrain(model_filter=model)
    except Exception as e:
        logger.error("Background retrain failed: %s", e)


@router.get("/models")
def ml_models() -> List[Dict[str, Any]]:
    """List all registered models with evaluation metrics."""
    try:
        from sqlalchemy import select
        from app.db.base import SessionLocal
        from app.models.match_result import MLModelRecord

        db = SessionLocal()
        try:
            records = db.scalars(select(MLModelRecord).order_by(MLModelRecord.trained_at.desc())).all()
            return [
                {
                    "id": r.id,
                    "model_name": r.model_name,
                    "version": r.version,
                    "accuracy": r.accuracy,
                    "f1_score": r.f1_score,
                    "brier_score": r.brier_score,
                    "log_loss": r.log_loss,
                    "calibration_score": r.calibration_score,
                    "ensemble_weight": round(r.ensemble_weight, 4),
                    "training_samples": r.training_samples,
                    "feature_version": r.feature_version,
                    "data_snapshot_version": r.data_snapshot_version,
                    "calibration_status": r.calibration_status,
                    "requires_recalibration": r.requires_recalibration,
                    "is_active": r.is_active,
                    "trained_at": r.trained_at.isoformat() if r.trained_at else None,
                }
                for r in records
            ]
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/features")
def ml_features(
    home_team: str = Query(...),
    away_team: str = Query(...),
    match_date: Optional[date] = Query(None),
) -> Dict[str, Any]:
    """Return the computed feature vector for a match."""
    from ml.features import FEATURE_NAMES, build_feature_vector
    from etl.transform.normalize import canonical

    fv = build_feature_vector(
        home_team=canonical(home_team),
        away_team=canonical(away_team),
        match_date=match_date,
    )
    return {
        "home_team": fv.home_team,
        "away_team": fv.away_team,
        "match_date": str(fv.match_date),
        "feature_version": fv.version,
        "features": {
            name: round(float(val), 4)
            for name, val in zip(FEATURE_NAMES, fv.features)
        },
    }


@router.get("/feature-names")
def ml_feature_names() -> Dict[str, Any]:
    """Return feature names and descriptions."""
    from ml.features import FEATURE_NAMES, FEATURE_VERSION
    return {"feature_names": FEATURE_NAMES, "version": FEATURE_VERSION, "count": len(FEATURE_NAMES)}


@router.get("/explanations")
def ml_explanations(
    home_team: str = Query(...),
    away_team: str = Query(...),
    match_date: Optional[date] = Query(None),
    model: str = Query("xgboost", description="Model to use for SHAP"),
) -> Dict[str, Any]:
    """Return SHAP-based feature importance for a specific match."""
    from ml.ensemble import _compute_shap, _feature_importance_explanation
    from ml.features import build_feature_vector
    from etl.transform.normalize import canonical

    fv = build_feature_vector(
        home_team=canonical(home_team),
        away_team=canonical(away_team),
        match_date=match_date,
    )
    shap_vals = _compute_shap(model, fv)
    exp = _feature_importance_explanation(fv, shap_vals)

    return {
        "home_team": fv.home_team,
        "away_team": fv.away_team,
        "model": model,
        "top_positive": [
            {"name": f.name, "display_name": f.display_name,
             "value": round(f.value, 3), "impact": round(f.impact, 4)}
            for f in exp.top_positive
        ],
        "top_negative": [
            {"name": f.name, "display_name": f.display_name,
             "value": round(f.value, 3), "impact": round(f.impact, 4)}
            for f in exp.top_negative
        ],
        "shap_values": [round(v, 4) for v in (exp.shap_values or [])],
        "narrative": exp.narrative,
    }


@router.post("/etl/run")
def ml_etl_run(_user: AdminUser, background_tasks: BackgroundTasks):
    """Trigger the ETL pipeline to refresh data (admin only)."""
    if background_tasks:
        background_tasks.add_task(_do_etl)
    return {"status": "etl_started"}


def _do_etl() -> None:
    try:
        from etl.pipeline import run_full_pipeline
        run_full_pipeline()
    except Exception as e:
        logger.error("ETL pipeline failed: %s", e)
