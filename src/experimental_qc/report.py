"""Report and visualization generation."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from .qc import QCResult


def write_markdown_report(result: QCResult, output_path: str | Path, source: str) -> None:
    """Write a concise QC summary as Markdown."""
    issue_total = len(result.issues)
    lines = [
        "# Experimental Data QC Report",
        "",
        f"- **Source:** `{source}`",
        f"- **QC status:** **{result.status}**",
        f"- **Rows checked:** {result.row_count}",
        f"- **Columns checked:** {result.column_count}",
        f"- **Issues found:** {issue_total}",
        "",
        "## Issues by type",
        "",
    ]
    if result.issue_counts.empty:
        lines.append("No issues detected.")
    else:
        lines.extend(["| Issue | Count |", "|---|---:|"])
        lines.extend(f"| {name} | {count} |" for name, count in result.issue_counts.items())

    if not result.group_counts.empty:
        lines.extend(["", "## Group sizes", "", "| Group | Rows |", "|---|---:|"])
        lines.extend(f"| {group} | {count} |" for group, count in result.group_counts.items())

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Flags indicate observations that should be reviewed. They are not automatic exclusion decisions. Apply and document exclusion criteria consistently.",
            "",
        ]
    )
    Path(output_path).write_text("\n".join(lines), encoding="utf-8")


def plot_missing_values(df: pd.DataFrame, output_path: str | Path) -> None:
    """Plot missing-value counts for columns that contain missing data."""
    missing = df.isna().sum()
    missing = missing[missing > 0].sort_values()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    if missing.empty:
        ax.text(0.5, 0.5, "No missing values", ha="center", va="center", fontsize=14)
        ax.set_axis_off()
    else:
        missing.plot.barh(ax=ax, color="#4C78A8")
        ax.set_xlabel("Missing values")
        ax.set_ylabel("")
        ax.set_title("Missing values by column")
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)


def plot_numeric_distributions(df: pd.DataFrame, output_path: str | Path) -> None:
    """Plot histograms for numeric columns."""
    numeric = df.select_dtypes(include="number")
    if numeric.empty:
        return
    axes = numeric.hist(figsize=(10, max(4, 2.8 * len(numeric.columns))), bins=12, color="#72B7B2", edgecolor="white")
    fig = axes.ravel()[0].get_figure()
    for ax in axes.ravel():
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_ylabel("Count")
    fig.suptitle("Numeric distributions", y=1.01, fontsize=14)
    fig.tight_layout()
    fig.savefig(output_path, dpi=160, bbox_inches="tight")
    plt.close(fig)
