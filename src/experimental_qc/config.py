"""Configuration models and JSON loading."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class NumericRange:
    """Inclusive acceptable range for a numeric measurement."""

    minimum: float | None = None
    maximum: float | None = None


@dataclass(frozen=True)
class GroupSize:
    """Expected inclusive size range for each experimental group."""

    minimum: int | None = None
    maximum: int | None = None


@dataclass(frozen=True)
class QCConfig:
    """Rules controlling the quality-control checks."""

    id_column: str | None = None
    required_columns: tuple[str, ...] = ()
    numeric_ranges: dict[str, NumericRange] = field(default_factory=dict)
    categorical_columns: tuple[str, ...] = ()
    group_column: str | None = None
    expected_group_size: GroupSize = field(default_factory=GroupSize)
    outlier_columns: tuple[str, ...] = ()
    outlier_iqr_multiplier: float = 1.5

    @classmethod
    def from_json(cls, path: str | Path) -> "QCConfig":
        """Load and validate a QC configuration from JSON."""
        with Path(path).open(encoding="utf-8") as handle:
            raw: dict[str, Any] = json.load(handle)

        ranges = {
            column: NumericRange(
                minimum=limits.get("min"), maximum=limits.get("max")
            )
            for column, limits in raw.get("numeric_ranges", {}).items()
        }
        group_raw = raw.get("expected_group_size", {})
        multiplier = float(raw.get("outlier_iqr_multiplier", 1.5))
        if multiplier <= 0:
            raise ValueError("outlier_iqr_multiplier must be greater than zero")

        return cls(
            id_column=raw.get("id_column"),
            required_columns=tuple(raw.get("required_columns", [])),
            numeric_ranges=ranges,
            categorical_columns=tuple(raw.get("categorical_columns", [])),
            group_column=raw.get("group_column"),
            expected_group_size=GroupSize(
                minimum=group_raw.get("min"), maximum=group_raw.get("max")
            ),
            outlier_columns=tuple(raw.get("outlier_columns", [])),
            outlier_iqr_multiplier=multiplier,
        )
