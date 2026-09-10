"""SIDER 4.1 — drug names and drug -> side-effect (MedDRA) relationships.

Source: http://sideeffects.embl.de/  (Kuhn et al., SIDER 4.1, 2015)
Files (tab-separated, no header):

* ``drug_names.tsv``          : STITCH compound id, drug name
* ``meddra_all_se.tsv.gz``    : 6 cols -> stitch_flat, stitch_stereo,
  umls_label, meddra_type (LLT|PT), umls_meddra, side_effect_name

License: SIDER is released for academic / non-commercial use; MedDRA terms are
subject to MedDRA MSSO licensing. See docs/data.md.
"""

from __future__ import annotations

import gzip

import pandas as pd

from app.data.constants import SIDER_FILES, Source
from app.data.net import DownloadError, download_file
from app.data.sources.base import BaseSource, SourceUnavailable

_DRUG_NAMES = "drug_names.tsv"
_MEDDRA_SE = "meddra_all_se.tsv.gz"


class SiderSource(BaseSource):
    source = Source.SIDER
    description = "SIDER 4.1 drug side-effect resource"
    license_note = "Academic/non-commercial use; MedDRA terms under MSSO licence."

    _required = (_DRUG_NAMES, _MEDDRA_SE)

    def download(self, *, force: bool = False) -> None:
        self.paths.raw_source_dir(self.source, create=True)
        errors: list[str] = []
        for name in self._required:
            url = SIDER_FILES[name]
            try:
                download_file(url, self.raw_dir / name, force=force)
            except DownloadError as exc:
                errors.append(f"{name}: {exc}")
        if errors:
            raise SourceUnavailable("SIDER download failed: " + "; ".join(errors))

    def available(self) -> bool:
        return all((self.raw_dir / n).exists() for n in self._required)

    # -- parsing ---------------------------------------------------------
    def extract_drugs(self) -> pd.DataFrame:
        self.ensure_available()
        df = pd.read_csv(
            self.raw_dir / _DRUG_NAMES,
            sep="\t",
            header=None,
            names=["stitch_id", "drug_name"],
            dtype=str,
            on_bad_lines="skip",
        )
        return df.dropna(subset=["stitch_id"])

    def extract_side_effects(self) -> pd.DataFrame:
        self.ensure_available()
        with gzip.open(self.raw_dir / _MEDDRA_SE, "rt") as fh:
            df = pd.read_csv(
                fh,
                sep="\t",
                header=None,
                names=[
                    "stitch_flat",
                    "stitch_stereo",
                    "umls_label",
                    "meddra_type",
                    "umls_meddra",
                    "side_effect_name",
                ],
                dtype=str,
                on_bad_lines="skip",
            )
        # Preferred Terms only: avoids many near-duplicate lower-level terms.
        df = df[df["meddra_type"] == "PT"].copy()
        df["umls_cui"] = df["umls_meddra"].fillna(df["umls_label"])
        return df[["stitch_flat", "umls_cui", "side_effect_name"]].rename(
            columns={"stitch_flat": "stitch_id"}
        )
