"""Decide whether refreshed data warrants model recalibration/retraining."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.base import SessionLocal  # noqa: E402
from app.models.match_result import MLModelRecord  # noqa: E402
from app.models.player import PlayerRatingImport  # noqa: E402
from app.models.ranking import RankingSourceLog  # noqa: E402
from app.models.team import EloSourceLog  # noqa: E402
from app.services.data_refresh_service import get_data_freshness_from_db  # noqa: E402


def evaluate_retraining_need(
    *,
    material_ranking_changes: int = 0,
    material_elo_changes: int = 0,
    changed_player_records: int = 0,
    changed_match_results: int = 0,
    apply: bool = False,
) -> dict[str, Any]:
    db = SessionLocal()
    try:
        reasons: list[str] = []
        action = "none"
        if material_ranking_changes >= 5:
            reasons.append(f"{material_ranking_changes} material FIFA ranking changes")
            action = "recalibration"
        if material_elo_changes >= 10:
            reasons.append(f"{material_elo_changes} material Elo changes")
            action = "recalibration"
        if changed_player_records >= 100:
            reasons.append(f"{changed_player_records} player records changed")
            action = "retraining"
        if changed_match_results == 1 and action == "none":
            reasons.append("single match result changed")
            action = "refresh_features_and_cache"

        freshness = get_data_freshness_from_db(db)
        latest_fifa_log = db.scalar(select(RankingSourceLog).order_by(RankingSourceLog.started_at.desc()).limit(1))
        latest_elo_log = db.scalar(select(EloSourceLog).order_by(EloSourceLog.started_at.desc()).limit(1))
        latest_player_import = db.scalar(select(PlayerRatingImport).order_by(PlayerRatingImport.imported_at.desc()).limit(1))

        models_marked = 0
        if apply and action in {"recalibration", "retraining"}:
            records = db.scalars(select(MLModelRecord).where(MLModelRecord.is_active.is_(True))).all()
            for record in records:
                record.requires_recalibration = True
                record.calibration_status = "requires_retraining" if action == "retraining" else "requires_recalibration"
                record.data_snapshot_version = freshness.get("data_snapshot_version")
                note = "; ".join(reasons)
                record.notes = f"{record.notes or ''}\n{action}: {note}".strip()
                models_marked += 1
            db.commit()

        return {
            "status": "ok",
            "action": action,
            "should_recalibrate": action in {"recalibration", "retraining"},
            "should_retrain": action == "retraining",
            "reasons": reasons,
            "models_marked": models_marked,
            "data_snapshot_version": freshness.get("data_snapshot_version"),
            "latest_sources": {
                "fifa": latest_fifa_log.data_version if latest_fifa_log else None,
                "elo": latest_elo_log.data_version if latest_elo_log else None,
                "players": latest_player_import.source_version if latest_player_import else None,
            },
        }
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate whether WCIP models need recalibration.")
    parser.add_argument("--material-ranking-changes", type=int, default=0)
    parser.add_argument("--material-elo-changes", type=int, default=0)
    parser.add_argument("--changed-player-records", type=int, default=0)
    parser.add_argument("--changed-match-results", type=int, default=0)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    report = evaluate_retraining_need(
        material_ranking_changes=args.material_ranking_changes,
        material_elo_changes=args.material_elo_changes,
        changed_player_records=args.changed_player_records,
        changed_match_results=args.changed_match_results,
        apply=args.apply,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
