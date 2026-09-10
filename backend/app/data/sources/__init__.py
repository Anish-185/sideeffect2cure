"""Source adapters: download + parse third-party biomedical data.

Each adapter is responsible only for turning a real public source into tidy
pandas frames with documented columns. Identifier normalization, deduplication
and internal-id minting happen later, in :mod:`app.data.ingest`.
"""

from app.data.sources.base import BaseSource, SourceUnavailable
from app.data.sources.chembl import ChemblSource
from app.data.sources.opentargets import OpenTargetsSource
from app.data.sources.reactome import ReactomeSource
from app.data.sources.sider import SiderSource

ALL_SOURCES: list[type[BaseSource]] = [
    SiderSource,
    ChemblSource,
    OpenTargetsSource,
    ReactomeSource,
]

__all__ = [
    "ALL_SOURCES",
    "BaseSource",
    "ChemblSource",
    "OpenTargetsSource",
    "ReactomeSource",
    "SiderSource",
    "SourceUnavailable",
]
