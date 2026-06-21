"""Probability normalization helpers shared by prediction services."""
from __future__ import annotations

import math
from collections.abc import Mapping


def normalize_probability_value(value: float | int | None) -> float:
    """Return a finite probability in the closed interval [0.0, 1.0]."""

    if value is None:
        return 0.0
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(numeric):
        return 0.0
    return max(0.0, min(1.0, numeric))


def normalize_probabilities(values: Mapping[str, float | int | None]) -> dict[str, float]:
    """Normalize finite, nonnegative weights into a probability distribution."""

    clean: dict[str, float] = {}
    for key, value in values.items():
        try:
            numeric = float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            numeric = 0.0
        clean[key] = max(0.0, numeric) if math.isfinite(numeric) else 0.0

    total = sum(clean.values())
    if total <= 0:
        count = max(len(clean), 1)
        return {key: 1.0 / count for key in clean}
    return {key: value / total for key, value in clean.items()}


def validate_probability_distribution(
    values: Mapping[str, float | int | None],
    *,
    tolerance: float = 0.01,
) -> bool:
    """Validate that values are bounded probabilities summing to about 1.0."""

    if not values:
        return False
    total = 0.0
    for value in values.values():
        try:
            numeric = float(value) if value is not None else 0.0
        except (TypeError, ValueError):
            return False
        if not math.isfinite(numeric) or numeric < 0.0 or numeric > 1.0:
            return False
        total += numeric
    return abs(total - 1.0) <= tolerance
