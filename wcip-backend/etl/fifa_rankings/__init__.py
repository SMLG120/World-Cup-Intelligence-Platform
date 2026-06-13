"""Dedicated FIFA ranking ETL package.

The implementation delegates to the existing official FIFA snapshot modules so
there is one canonical ingestion path and one database representation.
"""

from etl.fifa_rankings.load_fifa_rankings import load_latest_fifa_rankings

__all__ = ["load_latest_fifa_rankings"]
