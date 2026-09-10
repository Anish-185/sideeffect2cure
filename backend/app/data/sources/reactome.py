"""Reactome — pathway names and Ensembl gene -> pathway mappings (human).

Source: https://reactome.org/  (current release flat files)

* ``ReactomePathways.txt``  : stable_id, pathway_name, species
* ``Ensembl2Reactome.txt``  : ensembl_id, reactome_stable_id, url,
  pathway_name, evidence_code, species  (lowest-level pathways)

License: Reactome is released under CC0 (public domain).
"""

from __future__ import annotations

import pandas as pd

from app.data.constants import (
    ENSEMBL_GENE_PREFIX,
    REACTOME_FILES,
    REACTOME_HUMAN_SPECIES,
    Source,
)
from app.data.net import DownloadError, download_file
from app.data.sources.base import BaseSource, SourceUnavailable

_PATHWAYS = "ReactomePathways.txt"
_ENSEMBL2REACTOME = "Ensembl2Reactome.txt"


class ReactomeSource(BaseSource):
    source = Source.REACTOME
    description = "Reactome pathway database (human subset)"
    license_note = "CC0 1.0 (public domain)."

    _required = (_PATHWAYS, _ENSEMBL2REACTOME)

    def download(self, *, force: bool = False) -> None:
        self.paths.raw_source_dir(self.source, create=True)
        errors: list[str] = []
        for name, url in REACTOME_FILES.items():
            try:
                download_file(url, self.raw_dir / name, force=force)
            except DownloadError as exc:
                errors.append(f"{name}: {exc}")
        if errors:
            raise SourceUnavailable("Reactome download failed: " + "; ".join(errors))

    def available(self) -> bool:
        return all((self.raw_dir / n).exists() for n in self._required)

    # -- parsing ---------------------------------------------------------
    def extract_pathways(self) -> pd.DataFrame:
        self.ensure_available()
        df = pd.read_csv(
            self.raw_dir / _PATHWAYS,
            sep="\t",
            header=None,
            names=["reactome_id", "pathway_name", "species"],
            dtype=str,
            on_bad_lines="skip",
        )
        return df[df["species"] == REACTOME_HUMAN_SPECIES][
            ["reactome_id", "pathway_name"]
        ].reset_index(drop=True)

    def extract_gene_pathways(self) -> pd.DataFrame:
        self.ensure_available()
        df = pd.read_csv(
            self.raw_dir / _ENSEMBL2REACTOME,
            sep="\t",
            header=None,
            names=[
                "ensembl_id",
                "reactome_id",
                "url",
                "pathway_name",
                "evidence_code",
                "species",
            ],
            dtype=str,
            on_bad_lines="skip",
        )
        df = df[
            (df["species"] == REACTOME_HUMAN_SPECIES)
            & df["ensembl_id"].str.startswith(ENSEMBL_GENE_PREFIX, na=False)
        ]
        return df[["ensembl_id", "reactome_id", "pathway_name", "evidence_code"]].reset_index(
            drop=True
        )
