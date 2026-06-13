"""Versioned World Football Elo ingestion pipeline."""

from etl.elo.load_elo import load_elo_snapshot, load_latest_elo_snapshot

__all__ = ["load_elo_snapshot", "load_latest_elo_snapshot"]
