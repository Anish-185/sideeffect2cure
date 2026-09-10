"""HGNC gene-identity bridge for Level 4 candidate generation.

The disease side (Open Targets) identifies genes by **Ensembl gene id**; the
drug-target side (ChEMBL) identifies proteins by **UniProt accession**. To
connect "disease gene X" to "drug target X" without string-matching gene names
we need an authoritative identity map.

That map is the **HGNC complete set** (`hgnc_complete_set.txt`, public / CC0),
which for every human gene lists its ``hgnc_id``, approved ``symbol``,
``ensembl_gene_id`` and ``uniprot_ids``. We use it only to derive:

    ensembl_gene_id  -> hgnc_id
    uniprot accession -> hgnc_id

and then candidates join on ``hgnc_id`` — a pure identifier match. Nothing is
invented: unmapped ids simply do not produce a gene-target candidate.

Best-effort: if the file is neither cached nor retrievable the gene-target route
is reported unavailable and the pathway route still runs.
"""

from __future__ import annotations

import functools
from pathlib import Path

import pandas as pd

from app.core.config import get_settings
from app.data.net import DownloadError, download_file
from app.data.paths import DataPaths

_HGNC_FILE = "hgnc_complete_set.txt"
_HGNC_URL = (
    "https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/hgnc_complete_set.txt"
)


class HGNCBridgeUnavailable(RuntimeError):
    pass


def _raw_path() -> Path:
    return DataPaths.from_settings(get_settings()).raw / "hgnc" / _HGNC_FILE


class HGNCBridge:
    """``ensembl_gene_id`` / ``uniprot`` -> ``hgnc_id`` (+ approved symbol)."""

    def __init__(
        self,
        ensembl_to_hgnc: dict[str, str],
        uniprot_to_hgnc: dict[str, str],
        hgnc_to_symbol: dict[str, str],
    ) -> None:
        self._ens = ensembl_to_hgnc
        self._uni = uniprot_to_hgnc
        self._sym = hgnc_to_symbol

    @property
    def size(self) -> int:
        return len(self._sym)

    def hgnc_for_ensembl(self, ensembl_gene_id: str | None) -> str | None:
        if not ensembl_gene_id:
            return None
        return self._ens.get(str(ensembl_gene_id).split(".", 1)[0].strip().upper())

    def hgnc_for_uniprot(self, uniprot: str | None) -> str | None:
        if not uniprot:
            return None
        return self._uni.get(str(uniprot).strip().upper())

    def symbol_for_hgnc(self, hgnc_id: str | None) -> str | None:
        if not hgnc_id:
            return None
        return self._sym.get(hgnc_id)


def _load_from_file(path: Path) -> HGNCBridge:
    df = pd.read_csv(
        path,
        sep="\t",
        dtype=str,
        low_memory=False,
        usecols=["hgnc_id", "symbol", "ensembl_gene_id", "uniprot_ids"],
    )
    ens: dict[str, str] = {}
    uni: dict[str, str] = {}
    sym: dict[str, str] = {}
    for r in df.itertuples(index=False):
        hgnc = r.hgnc_id
        if not isinstance(hgnc, str) or not hgnc:
            continue
        if isinstance(r.symbol, str) and r.symbol:
            sym[hgnc] = r.symbol
        if isinstance(r.ensembl_gene_id, str) and r.ensembl_gene_id.startswith("ENSG"):
            ens.setdefault(r.ensembl_gene_id.strip().upper(), hgnc)
        if isinstance(r.uniprot_ids, str):
            for acc in r.uniprot_ids.split("|"):
                acc = acc.strip().upper()
                if acc:
                    uni.setdefault(acc, hgnc)
    return HGNCBridge(ens, uni, sym)


@functools.cache
def get_hgnc_bridge(*, allow_download: bool = True) -> HGNCBridge:
    path = _raw_path()
    if not path.exists() or path.stat().st_size == 0:
        if not allow_download:
            raise HGNCBridgeUnavailable(f"{path} not cached and downloads disabled")
        try:
            download_file(_HGNC_URL, path)
        except DownloadError as exc:
            raise HGNCBridgeUnavailable(f"could not fetch {_HGNC_URL}: {exc}") from exc
    try:
        return _load_from_file(path)
    except (OSError, ValueError) as exc:
        raise HGNCBridgeUnavailable(f"could not parse {path}: {exc}") from exc


def reset_hgnc_bridge() -> None:
    get_hgnc_bridge.cache_clear()
