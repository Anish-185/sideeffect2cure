"""Cross-table data-quality checks run on the processed datasets.

These are the checks the brief calls out explicitly:

* no invalid / missing required ids
* no duplicate primary-entity ids
* no duplicate relationships
* reasonable missing-value levels
* referential integrity between relationship tables and entity tables
"""

from __future__ import annotations

import pandas as pd

from app.data.constants import PRIMARY_KEYS, REFERENTIAL_INTEGRITY, Dataset
from app.data.paths import DataPaths
from app.data.report import PipelineReport, QualityCheck

# Fraction of NULLs in an *optional* column above which we emit a warning.
_MISSING_WARN_THRESHOLD = 0.60


def load_processed(paths: DataPaths) -> dict[Dataset, pd.DataFrame]:
    frames: dict[Dataset, pd.DataFrame] = {}
    for ds in Dataset:
        p = paths.processed_parquet(ds)
        if p.exists():
            frames[ds] = pd.read_parquet(p)
    return frames


def run_quality_checks(
    frames: dict[Dataset, pd.DataFrame], report: PipelineReport
) -> None:
    present = set(frames)

    # 1. required *internal* id columns non-null + non-empty
    #    (these are exactly the primary-key columns; ``*_id`` columns like
    #    ``chembl_id`` / ``ensembl_id`` hold optional external ids)
    for ds, df in frames.items():
        id_cols = [c for c in PRIMARY_KEYS[ds] if c in df.columns]
        offenders = {c: int(df[c].isna().sum() + (df[c] == "").sum()) for c in id_cols}
        bad = {c: n for c, n in offenders.items() if n}
        report.add_check(
            QualityCheck(
                name=f"{ds.value}: required ids populated",
                passed=not bad,
                detail="" if not bad else f"nulls/empties: {bad}",
            )
        )

    # 2. no duplicate primary keys
    for ds, df in frames.items():
        pk = list(PRIMARY_KEYS[ds])
        n_dup = int(df.duplicated(subset=pk).sum())
        report.add_check(
            QualityCheck(
                name=f"{ds.value}: unique primary key {tuple(pk)}",
                passed=n_dup == 0,
                detail="" if n_dup == 0 else f"{n_dup} duplicate rows",
            )
        )

    # 3. referential integrity
    for rel_ds, refs in REFERENTIAL_INTEGRITY.items():
        if rel_ds not in present:
            continue
        rel = frames[rel_ds]
        for col, entity_ds in refs:
            if entity_ds not in present:
                report.add_check(
                    QualityCheck(
                        name=f"{rel_ds.value}.{col} -> {entity_ds.value}",
                        passed=False,
                        detail=f"{entity_ds.value} table missing",
                    )
                )
                continue
            entity_pk = PRIMARY_KEYS[entity_ds][0]
            known = set(frames[entity_ds][entity_pk])
            orphan_mask = ~rel[col].isin(known)
            n_orphan = int(orphan_mask.sum())
            report.add_check(
                QualityCheck(
                    name=f"{rel_ds.value}.{col} -> {entity_ds.value}.{entity_pk}",
                    passed=n_orphan == 0,
                    detail="" if n_orphan == 0 else f"{n_orphan} orphan rows",
                )
            )

    # 4. missing-value levels on optional columns (warning only)
    for ds, df in frames.items():
        if df.empty:
            continue
        internal_ids = set(PRIMARY_KEYS[ds])
        for col in df.columns:
            if col in internal_ids:
                continue
            frac = float(df[col].isna().mean())
            if frac >= _MISSING_WARN_THRESHOLD:
                report.add_check(
                    QualityCheck(
                        name=f"{ds.value}.{col}: missing-value level",
                        passed=False,
                        severity="warning",
                        detail=f"{frac:.0%} null",
                    )
                )

    # 5. non-empty core datasets (warning if a table came out empty)
    for ds in (Dataset.DRUGS, Dataset.DISEASES):
        if ds in frames:
            report.add_check(
                QualityCheck(
                    name=f"{ds.value}: non-empty",
                    passed=not frames[ds].empty,
                    severity="warning",
                    detail="" if not frames[ds].empty else "0 rows",
                )
            )
