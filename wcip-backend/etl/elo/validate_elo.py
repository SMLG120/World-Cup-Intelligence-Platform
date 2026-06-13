"""Validation for World Football Elo snapshots."""
from __future__ import annotations

from dataclasses import dataclass, field

from etl.elo.transform_elo import EloSnapshot


@dataclass
class EloValidationReport:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def validate_elo_snapshot(snapshot: EloSnapshot, *, min_records: int = 20) -> EloValidationReport:
    errors: list[str] = []
    warnings: list[str] = []

    if not snapshot.snapshot_id:
        errors.append("missing snapshot_id")
    if len(snapshot.records) < min_records:
        errors.append(f"expected at least {min_records} Elo records; got {len(snapshot.records)}")

    names = [record.team_name for record in snapshot.records]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        errors.append(f"duplicate teams: {duplicates[:10]}")

    for record in snapshot.records:
        if not 500 <= float(record.rating) <= 2500:
            errors.append(f"{record.team_name} has implausible Elo rating {record.rating}")
        if record.rank is not None and record.rank <= 0:
            errors.append(f"{record.team_name} has invalid Elo rank {record.rank}")

    ranked = [record.rank for record in snapshot.records if record.rank is not None]
    if ranked and min(ranked) != 1:
        warnings.append("Elo ranks do not start at 1")
    if ranked and len(ranked) != len(set(ranked)):
        warnings.append("Elo ranks contain duplicates")

    return EloValidationReport(ok=not errors, errors=errors, warnings=warnings)


def assert_valid_elo_snapshot(snapshot: EloSnapshot, *, min_records: int = 20) -> None:
    report = validate_elo_snapshot(snapshot, min_records=min_records)
    if not report.ok:
        raise ValueError("; ".join(report.errors))
