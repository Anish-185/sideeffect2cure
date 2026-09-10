#!/usr/bin/env python3
"""Run the Level 1 biomedical data ingestion pipeline.

Examples
--------
    python scripts/ingest_data.py                 # all sources, download as needed
    python scripts/ingest_data.py --offline       # rebuild from already-downloaded raw
    python scripts/ingest_data.py --sources sider reactome
    python scripts/ingest_data.py --force         # re-download raw inputs

Exit code is non-zero if any hard data-quality check fails.
"""

from __future__ import annotations

import argparse
import sys

import _bootstrap  # noqa: F401

from app.data.constants import Source
from app.data.ingest import run_ingestion


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=[s.value for s in Source if s not in (Source.DERIVED, Source.PUBCHEM)],
        help="subset of sources to ingest (default: all)",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="do not hit the network; rebuild from raw/ that already exists",
    )
    parser.add_argument(
        "--force", action="store_true", help="re-download raw inputs even if cached"
    )
    args = parser.parse_args(argv)

    selected = [Source(s) for s in args.sources] if args.sources else None
    report = run_ingestion(sources=selected, offline=args.offline, force=args.force)
    print(report.render())
    if report.hard_failures:
        print("\nHARD FAILURES:")
        for c in report.hard_failures:
            print(f"  - {c.name}: {c.detail}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
