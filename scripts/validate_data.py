#!/usr/bin/env python3
"""Run data-quality / referential-integrity checks on the processed datasets.

    python scripts/validate_data.py

Reads ``data/processed/*.parquet`` (does not touch the network) and re-runs the
cross-table quality checks. Exit code is non-zero on any hard failure.
"""

from __future__ import annotations

import sys

import _bootstrap  # noqa: F401

from app.core.config import get_settings
from app.data.loaders import available_datasets
from app.data.paths import DataPaths
from app.data.quality import load_processed, run_quality_checks
from app.data.report import PipelineReport


def main() -> int:
    paths = DataPaths.from_settings(get_settings())
    built = available_datasets()
    if not built:
        print("No processed datasets found - run scripts/ingest_data.py first.")
        return 1

    frames = load_processed(paths)
    report = PipelineReport(kind="validation")
    report.dataset_counts = {ds.value: len(df) for ds, df in frames.items()}
    run_quality_checks(frames, report)
    report.write(paths.report_json("validation"))
    print(report.render())
    return 1 if report.hard_failures else 0


if __name__ == "__main__":
    sys.exit(main())
