"""Command-line interface for experimental data QC."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .config import QCConfig
from .qc import run_qc
from .report import plot_missing_values, plot_numeric_distributions, write_markdown_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="experimental-qc",
        description="Check a biological experiment CSV and generate a QC report.",
    )
    parser.add_argument("csv", type=Path, help="Input experiment CSV")
    parser.add_argument("--config", type=Path, help="Optional JSON rules file")
    parser.add_argument("--output", type=Path, default=Path("qc_output"), help="Output directory")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.csv.exists():
        raise SystemExit(f"Input file not found: {args.csv}")

    config = QCConfig.from_json(args.config) if args.config else QCConfig()
    df = pd.read_csv(args.csv)
    result = run_qc(df, config)

    args.output.mkdir(parents=True, exist_ok=True)
    result.issues.to_csv(args.output / "qc_issues.csv", index=False)
    write_markdown_report(result, args.output / "qc_report.md", args.csv.name)
    plot_missing_values(df, args.output / "missing_values.png")
    plot_numeric_distributions(df, args.output / "numeric_distributions.png")

    print(f"QC status: {result.status}")
    print(f"Rows checked: {result.row_count}")
    print(f"Issues found: {len(result.issues)}")
    print(f"Report: {args.output / 'qc_report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
