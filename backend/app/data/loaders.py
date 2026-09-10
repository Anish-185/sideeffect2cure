"""Read-only access to the processed datasets, for use by later levels.

Later levels should import from here rather than touching ``data/processed``
paths directly.
"""

from __future__ import annotations

import pandas as pd

from app.core.config import get_settings
from app.data.constants import Dataset
from app.data.paths import DataPaths


class DatasetsNotBuilt(FileNotFoundError):
    pass


def _paths() -> DataPaths:
    return DataPaths.from_settings(get_settings())


def load_dataset(dataset: Dataset | str) -> pd.DataFrame:
    ds = Dataset(dataset) if not isinstance(dataset, Dataset) else dataset
    path = _paths().processed_parquet(ds)
    if not path.exists():
        raise DatasetsNotBuilt(
            f"{path} not found - run `python -m scripts.ingest_data` first"
        )
    return pd.read_parquet(path)


def load_identifier_map() -> pd.DataFrame:
    path = _paths().mapping_parquet()
    if not path.exists():
        raise DatasetsNotBuilt(f"{path} not found - run ingestion first")
    return pd.read_parquet(path)


def available_datasets() -> list[str]:
    p = _paths()
    return [ds.value for ds in Dataset if p.processed_parquet(ds).exists()]
