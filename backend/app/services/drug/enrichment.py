"""Optional biological-context enrichment for the drug profile.

The ONE optional source integrated at Level 3 is **Reactome**, used for exactly
one thing that the Level 1 data does not already provide:

    drug -> ChEMBL target -> UniProt accession -> Reactome pathway

This mirrors the Level 2 disease-pathway layer, so later levels can compare a
drug's pathway footprint with a disease's. It reuses a source Level 1 already
integrated (Reactome, CC0) and a single extra flat file
(``UniProt2Reactome.txt``), cached under ``data/raw/reactome/``.

It is strictly best-effort: if the file is not cached and cannot be downloaded,
the profile is built without pathway context (``pathway_context_available =
False``) and everything else still works.
"""

from __future__ import annotations

import functools
from pathlib import Path

import pandas as pd

from app.core.config import get_settings
from app.data.constants import REACTOME_BASE_URL, REACTOME_HUMAN_SPECIES, Source
from app.data.net import DownloadError, download_file
from app.data.paths import DataPaths

_UNIPROT2REACTOME_FILE = "UniProt2Reactome.txt"
_UNIPROT2REACTOME_URL = f"{REACTOME_BASE_URL}/{_UNIPROT2REACTOME_FILE}"
_MAX_PATHWAYS = 100


class PathwayEnrichmentUnavailable(RuntimeError):
    pass


def _raw_path() -> Path:
    return DataPaths.from_settings(get_settings()).raw_file(Source.REACTOME, _UNIPROT2REACTOME_FILE)


class ReactomeUniProtIndex:
    """uniprot accession -> [(reactome_id, pathway_name), ...] for human only."""

    def __init__(self, mapping: dict[str, list[tuple[str, str]]]) -> None:
        self._m = mapping

    @property
    def size(self) -> int:
        return len(self._m)

    def pathways_for(
        self, uniprot_ids: list[str], *, limit: int | None = _MAX_PATHWAYS
    ) -> list[dict]:
        """Aggregate pathways across a drug's targets, with support counts.

        ``limit`` caps the result (default keeps profiles lean); pass ``None`` for
        the full set (candidate generation needs every overlap).
        """
        agg: dict[str, dict] = {}
        for uid in dict.fromkeys(u for u in uniprot_ids if u):
            for reactome_id, name in self._m.get(uid.upper(), []):
                slot = agg.setdefault(
                    reactome_id,
                    {"reactome_id": reactome_id, "pathway_name": name, "uniprots": []},
                )
                slot["uniprots"].append(uid)
        rows = [
            {
                "reactome_id": v["reactome_id"],
                "pathway_name": v["pathway_name"],
                "supporting_target_count": len(v["uniprots"]),
                "supporting_uniprot_ids": list(dict.fromkeys(v["uniprots"])),
            }
            for v in agg.values()
        ]
        rows.sort(key=lambda r: (-r["supporting_target_count"], r["pathway_name"]))
        return rows if limit is None else rows[:limit]


def _load_index_from_file(path: Path) -> ReactomeUniProtIndex:
    # columns: uniprot, reactome_id, url, pathway_name, evidence_code, species
    df = pd.read_csv(
        path,
        sep="\t",
        header=None,
        names=["uniprot", "reactome_id", "url", "pathway_name", "evidence_code", "species"],
        dtype=str,
        on_bad_lines="skip",
    )
    df = df[df["species"] == REACTOME_HUMAN_SPECIES]
    mapping: dict[str, list[tuple[str, str]]] = {}
    for uid, rid, name in zip(df["uniprot"], df["reactome_id"], df["pathway_name"], strict=True):
        if not uid or not rid:
            continue
        mapping.setdefault(uid.strip().upper(), []).append((rid.strip(), str(name)))
    for k, v in mapping.items():
        mapping[k] = list(dict.fromkeys(v))
    return ReactomeUniProtIndex(mapping)


@functools.cache
def get_reactome_index(*, allow_download: bool = True) -> ReactomeUniProtIndex:
    """Load the cached UniProt->Reactome index, downloading the file once if needed.

    Raises :class:`PathwayEnrichmentUnavailable` if the file is neither cached
    nor retrievable. Result is memoised for the process.
    """
    path = _raw_path()
    if not path.exists() or path.stat().st_size == 0:
        if not allow_download:
            raise PathwayEnrichmentUnavailable(
                f"{path} not cached and downloads disabled"
            )
        try:
            download_file(_UNIPROT2REACTOME_URL, path)
        except DownloadError as exc:  # network down / source unreachable
            raise PathwayEnrichmentUnavailable(f"could not fetch {_UNIPROT2REACTOME_URL}: {exc}") from exc
    try:
        return _load_index_from_file(path)
    except (OSError, ValueError) as exc:
        raise PathwayEnrichmentUnavailable(f"could not parse {path}: {exc}") from exc


def reset_reactome_index() -> None:
    get_reactome_index.cache_clear()
