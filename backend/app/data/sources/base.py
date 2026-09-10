"""Base class for source adapters."""

from __future__ import annotations

import abc

from app.data.constants import Source
from app.data.paths import DataPaths


class SourceUnavailable(RuntimeError):
    """Raised when a source's raw inputs cannot be obtained.

    The pipeline catches this, records it in the report, and continues with the
    other sources rather than aborting the whole run.
    """


class BaseSource(abc.ABC):
    """Download + parse one third-party data source.

    Subclasses must not normalize identifiers or deduplicate — they return the
    data as the source presents it (with obvious parsing only).
    """

    source: Source
    #: human-facing description, shown in reports / docs
    description: str = ""
    #: licensing / attribution note surfaced in the report
    license_note: str = ""

    def __init__(self, paths: DataPaths) -> None:
        self.paths = paths

    @property
    def raw_dir(self):
        return self.paths.raw_source_dir(self.source)

    @abc.abstractmethod
    def download(self, *, force: bool = False) -> None:
        """Fetch raw inputs into ``self.raw_dir``. Raise SourceUnavailable on failure."""

    @abc.abstractmethod
    def available(self) -> bool:
        """True if the raw inputs needed for parsing are present on disk."""

    def ensure_available(self) -> None:
        if not self.available():
            raise SourceUnavailable(
                f"{self.source.value}: raw inputs missing in {self.raw_dir} "
                f"(run ingestion with network access)"
            )
