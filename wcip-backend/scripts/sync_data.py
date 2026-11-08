"""Authoritative football-data sync job.

This is the only process that talks to external data providers in
production. It runs as a Render Cron Job (see ``render.yaml``):

    python -m scripts.sync_data

Render fetches and validates; Supabase Postgres stores the versioned
snapshots; the Vercel frontend only reads them through the backend API.
Vercel and Supabase never fetch FIFA/Elo/results themselves.

Each step is idempotent and isolated: a failing provider is logged and leaves
the previously stored data untouched (see the validators in ``etl/``).

Exit codes: 0 = every step ok, 1 = some step failed (Render marks the run
failed and notifies), 2 = another sync is already running.
"""
from __future__ import annotations

import json
import logging
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from app.db.base import engine  # noqa: E402

logger = logging.getLogger("wcip.sync")

# Arbitrary constant key for pg_try_advisory_lock; unique to this job.
_ADVISORY_LOCK_KEY = 7_202_611


@contextmanager
def _single_run_lock():
    """Prevent overlapping runs (slow provider + next cron tick, manual run).

    Uses a *transaction-scoped* advisory lock held by one open transaction for
    the whole run. That works through Supabase's transaction pooler (port
    6543), which may move a session to another backend between transactions
    and would break a session-level lock/unlock pair. The lock is released
    when the transaction ends or the process dies, so a crash cannot wedge the
    schedule. SQLite (local dev) has no equivalent and runs unlocked.
    """

    if engine.dialect.name != "postgresql":
        yield True
        return
    with engine.connect() as conn, conn.begin():
        acquired = bool(
            conn.execute(text("SELECT pg_try_advisory_xact_lock(:k)"), {"k": _ADVISORY_LOCK_KEY}).scalar()
        )
        yield acquired


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    from app.services.data_refresh_service import refresh_all_live_football_data

    with _single_run_lock() as acquired:
        if not acquired:
            logger.warning("Another data sync holds the lock; exiting without work")
            return 2
        summary = refresh_all_live_football_data()

    compact = {
        "status": summary["status"],
        "started_at": summary["started_at"],
        "finished_at": summary["finished_at"],
        "steps": summary["steps"],
        "failures": {
            name: result.get("detail")
            for name, result in summary["results"].items()
            if result.get("status") != "ok"
        },
    }
    print(json.dumps(compact, indent=2, default=str))
    return 0 if summary["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
