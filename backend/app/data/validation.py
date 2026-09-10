"""Frame-level validation used *during* ingestion.

These checks run on a processed frame just before it is written. They confirm
the frame matches its schema; genuine data-quality / cross-table checks live in
:mod:`app.data.quality`.
"""

from __future__ import annotations

import pandas as pd
from pydantic import ValidationError

from app.data.constants import PRIMARY_KEYS, Dataset
from app.data.report import StageReport
from app.data.schemas import ROW_MODELS


def expected_columns(dataset: Dataset) -> list[str]:
    return list(ROW_MODELS[dataset.value].model_fields.keys())


def required_columns(dataset: Dataset) -> list[str]:
    model = ROW_MODELS[dataset.value]
    return [name for name, field in model.model_fields.items() if field.is_required()]


def coerce_and_validate(
    dataset: Dataset,
    df: pd.DataFrame,
    stage: StageReport,
    *,
    validate_rows: bool = True,
) -> pd.DataFrame:
    """Reorder to schema columns, drop rows failing the row model, dedupe PKs.

    Every dropped row is recorded in ``stage`` with a reason. Returns the clean
    frame.
    """
    model = ROW_MODELS[dataset.value]
    cols = expected_columns(dataset)
    df = df.copy()

    for c in cols:
        if c not in df.columns:
            df[c] = pd.NA
    df = df[cols]
    df = df.replace({"": pd.NA})
    stage.input_rows = len(df)

    # 1. required fields present + non-null
    required = required_columns(dataset)
    bad_required = df[df[required].isna().any(axis=1)]
    if len(bad_required):
        for _, row in bad_required.head(20).iterrows():
            stage.reject("missing_required_field", row.to_dict())
        stage.rejections["missing_required_field"].count = len(bad_required)
        df = df.drop(bad_required.index)

    # 2. row-model validation (types, score ranges, ...)
    if validate_rows and len(df):
        ok_idx: list = []
        for idx, record in zip(df.index, df.to_dict(orient="records"), strict=True):
            clean = {k: (None if pd.isna(v) else v) for k, v in record.items()}
            try:
                model.model_validate(clean)
            except ValidationError as exc:
                stage.reject("schema_violation", f"{clean} :: {exc.errors()[0].get('msg')}")
                continue
            ok_idx.append(idx)
        df = df.loc[ok_idx]

    # 3. deduplicate on primary key
    pk = list(PRIMARY_KEYS[dataset])
    dup_mask = df.duplicated(subset=pk, keep="first")
    n_dup = int(dup_mask.sum())
    if n_dup:
        for _, row in df[dup_mask].head(20).iterrows():
            stage.reject("duplicate_primary_key", {k: row[k] for k in pk})
        stage.rejections["duplicate_primary_key"].count = n_dup
        df = df[~dup_mask]

    df = df.reset_index(drop=True)
    stage.output_rows = len(df)
    return df
