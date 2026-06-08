"""WC2026-specific ETL package.

Provides a self-contained ingestion pipeline for:
  - All 48 qualified team records with extended stats
  - Official group assignments
  - One explicitly marked placeholder coach/player per team for local startup
  - Full coaches and squad players when a source snapshot is supplied

Data in seed_data.py is the authoritative source of truth for WC2026 team and
group metadata. Real squad and coach snapshots remain isolated from the generic
football-data ETL so future tournaments can be handled independently.

Usage:
    from etl.world_cup_2026.ingest import run_wc2026_seed
    run_wc2026_seed()
"""

