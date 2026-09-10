"""Filesystem layout for the data foundation.

A single object resolves every path the ingestion / validation code needs, so no
module hard-codes ``data/...`` strings. Directories are created on demand.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, get_settings
from app.data.constants import MAPPING_TABLE_NAME, Dataset, Source


@dataclass(frozen=True)
class DataPaths:
    root: Path
    raw: Path
    processed: Path
    mappings: Path
    reports: Path

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> DataPaths:
        s = settings or get_settings()
        return cls(
            root=s.data_dir,
            raw=s.raw_dir,
            processed=s.processed_dir,
            mappings=s.mappings_dir,
            reports=s.processed_dir / "_reports",
        )

    # -- raw ----------------------------------------------------------------
    def raw_source_dir(self, source: Source, *, create: bool = False) -> Path:
        p = self.raw / source.value
        if create:
            p.mkdir(parents=True, exist_ok=True)
        return p

    def raw_file(self, source: Source, filename: str, *, create_parent: bool = False) -> Path:
        p = self.raw_source_dir(source)
        if create_parent:
            p.mkdir(parents=True, exist_ok=True)
        return p / filename

    # -- processed --------------------------------------------------------
    def processed_parquet(self, dataset: Dataset) -> Path:
        return self.processed / f"{dataset.value}.parquet"

    def processed_csv(self, dataset: Dataset) -> Path:
        return self.processed / f"{dataset.value}.csv"

    def mapping_parquet(self) -> Path:
        return self.mappings / f"{MAPPING_TABLE_NAME}.parquet"

    def mapping_csv(self) -> Path:
        return self.mappings / f"{MAPPING_TABLE_NAME}.csv"

    def report_json(self, name: str) -> Path:
        return self.reports / f"{name}.json"

    def ensure_dirs(self) -> None:
        for p in (self.raw, self.processed, self.mappings, self.reports):
            p.mkdir(parents=True, exist_ok=True)
