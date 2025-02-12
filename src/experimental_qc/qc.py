"""Core quality-control checks."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .config import QCConfig

ISSUE_COLUMNS = ["row", "column", "issue_type", "value", "message"]


@dataclass
class QCResult:
    """Structured results returned by the QC pipeline."""

    row_count: int
    column_count: int
    issues: pd.DataFrame
    group_counts: pd.Series

    @property
    def status(self) -> str:
        """Return PASS when no issues exist, otherwise WARNING."""
        return "PASS" if self.issues.empty else "WARNING"

    @property
    def issue_counts(self) -> pd.Series:
        """Count issues by type."""
        if self.issues.empty:
            return pd.Series(dtype="int64")
        return self.issues["issue_type"].value_counts()


def _issue(
    row: object,
    column: str,
    issue_type: str,
    value: object,
    message: str,
) -> dict[str, object]:
    return {
        "row": row,
        "column": column,
        "issue_type": issue_type,
        "value": value,
        "message": message,
    }


def _check_missing(df: pd.DataFrame, config: QCConfig) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for column in config.required_columns:
        if column not in df.columns:
            issues.append(
                _issue("dataset", column, "missing_column", "", f"Required column '{column}' is absent")
            )
            continue
        for index in df.index[df[column].isna()]:
            issues.append(
                _issue(index, column, "missing_required", "", "Required value is missing")
            )
    return issues


def _check_duplicates(df: pd.DataFrame, config: QCConfig) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    if config.id_column and config.id_column in df.columns:
        duplicated = df[config.id_column].notna() & df[config.id_column].duplicated(keep=False)
        for index in df.index[duplicated]:
            value = df.at[index, config.id_column]
            issues.append(
                _issue(index, config.id_column, "duplicate_id", value, "Sample ID is not unique")
            )

    for index in df.index[df.duplicated(keep=False)]:
        issues.append(
            _issue(index, "all", "duplicate_row", "", "Entire row is duplicated")
        )
    return issues


def _check_ranges(df: pd.DataFrame, config: QCConfig) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for column, limits in config.numeric_ranges.items():
        if column not in df.columns:
            continue
        numeric = pd.to_numeric(df[column], errors="coerce")
        invalid_numeric = df[column].notna() & numeric.isna()
        for index in df.index[invalid_numeric]:
            issues.append(
                _issue(index, column, "non_numeric", df.at[index, column], "Expected a numeric value")
            )

        out_of_range = pd.Series(False, index=df.index)
        if limits.minimum is not None:
            out_of_range |= numeric < limits.minimum
        if limits.maximum is not None:
            out_of_range |= numeric > limits.maximum
        for index in df.index[out_of_range.fillna(False)]:
            issues.append(
                _issue(index, column, "out_of_range", df.at[index, column], "Value falls outside configured limits")
            )
    return issues


def _check_outliers(df: pd.DataFrame, config: QCConfig) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for column in config.outlier_columns:
        if column not in df.columns:
            continue
        numeric = pd.to_numeric(df[column], errors="coerce").dropna()
        if len(numeric) < 4:
            continue
        q1, q3 = numeric.quantile([0.25, 0.75])
        iqr = q3 - q1
        if iqr == 0:
            continue
        lower = q1 - config.outlier_iqr_multiplier * iqr
        upper = q3 + config.outlier_iqr_multiplier * iqr
        flagged = numeric[(numeric < lower) | (numeric > upper)]
        for index, value in flagged.items():
            issues.append(
                _issue(index, column, "statistical_outlier", value, f"Outside IQR bounds [{lower:.3g}, {upper:.3g}]")
            )
    return issues


def _normalize_label(value: object) -> str:
    return " ".join(str(value).strip().lower().split())


def _check_labels(df: pd.DataFrame, config: QCConfig) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for column in config.categorical_columns:
        if column not in df.columns:
            continue
        present = df[column].dropna().astype(str)
        normalized_to_originals: dict[str, set[str]] = {}
        for value in present:
            normalized_to_originals.setdefault(_normalize_label(value), set()).add(value)

        inconsistent = {
            normalized
            for normalized, originals in normalized_to_originals.items()
            if len(originals) > 1
        }
        for index, value in present.items():
            normalized = _normalize_label(value)
            if normalized in inconsistent:
                variants = sorted(normalized_to_originals[normalized])
                issues.append(
                    _issue(index, column, "inconsistent_label", value, f"Equivalent labels found: {variants}")
                )
    return issues


def _check_group_sizes(
    df: pd.DataFrame, config: QCConfig
) -> tuple[list[dict[str, object]], pd.Series]:
    if not config.group_column or config.group_column not in df.columns:
        return [], pd.Series(dtype="int64")

    counts = df[config.group_column].value_counts(dropna=False)
    issues: list[dict[str, object]] = []
    for group, count in counts.items():
        too_small = (
            config.expected_group_size.minimum is not None
            and count < config.expected_group_size.minimum
        )
        too_large = (
            config.expected_group_size.maximum is not None
            and count > config.expected_group_size.maximum
        )
        if too_small or too_large:
            issues.append(
                _issue("group", config.group_column, "unexpected_group_size", group, f"Group contains {count} rows")
            )
    return issues, counts


def run_qc(df: pd.DataFrame, config: QCConfig | None = None) -> QCResult:
    """Run all configured checks and return structured findings."""
    config = config or QCConfig()
    issues: list[dict[str, object]] = []
    issues.extend(_check_missing(df, config))
    issues.extend(_check_duplicates(df, config))
    issues.extend(_check_ranges(df, config))
    issues.extend(_check_outliers(df, config))
    issues.extend(_check_labels(df, config))
    group_issues, group_counts = _check_group_sizes(df, config)
    issues.extend(group_issues)

    issue_frame = pd.DataFrame(issues, columns=ISSUE_COLUMNS)
    if not issue_frame.empty:
        issue_frame = issue_frame.sort_values(["issue_type", "row"], key=lambda s: s.astype(str)).reset_index(drop=True)
    return QCResult(len(df), len(df.columns), issue_frame, group_counts)
