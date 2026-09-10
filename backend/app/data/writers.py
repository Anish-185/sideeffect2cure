"""Persist processed frames as parquet (canonical) + CSV (inspection)."""

from __future__ import annotations

import pandas as pd

from app.data.constants import Dataset
from app.data.paths import DataPaths
from app.data.validation import expected_columns


def write_dataset(paths: DataPaths, dataset: Dataset, df: pd.DataFrame) -> None:
    cols = expected_columns(dataset)
    df = df.reindex(columns=cols)
    paths.processed.mkdir(parents=True, exist_ok=True)
    df.to_parquet(paths.processed_parquet(dataset), index=False)
    df.to_csv(paths.processed_csv(dataset), index=False)


def write_mapping(paths: DataPaths, df: pd.DataFrame) -> None:
    paths.mappings.mkdir(parents=True, exist_ok=True)
    df.to_parquet(paths.mapping_parquet(), index=False)
    df.to_csv(paths.mapping_csv(), index=False)
