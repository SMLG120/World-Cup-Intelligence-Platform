"""Compatibility facade for the dedicated WC2026 seed ETL module."""
from etl.world_cup_2026.ingest import (  # noqa: F401
    CoachSeedRecord,
    PlayerSeedRecord,
    TeamSeedRecord,
    WC2026SeedPayload,
    normalize_seed_payload,
    run_wc2026_seed,
)
