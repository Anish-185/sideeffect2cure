"""ChEMBL — drug -> target (mechanism of action) + canonical drug identifiers.

Source: https://www.ebi.ac.uk/chembl/  (ChEMBL REST API, current release)

Pulled (all small / targeted):

* the full ``mechanism`` table (curated drug mechanism-of-action -> target;
  ~7.5k rows) and the ``target`` records it references;
* a PubChem-CID -> ChEMBL-id map for the SIDER drug set, resolved via PubChem
  PUG-REST synonyms (PubChem registers ChEMBL ids as compound synonyms). This
  replaces the multi-hundred-MB UniChem whole-source mapping with a handful of
  batched requests scoped to the drugs we actually have.

License: ChEMBL is released under CC BY-SA 3.0; PubChem data is public domain.
"""

from __future__ import annotations

import json
import time

import pandas as pd

from app.data import identifiers as idn
from app.data.constants import (
    CHEMBL_API_BASE,
    PUBCHEM_CID_BATCH,
    PUBCHEM_PUG_REST,
    Source,
)
from app.data.net import DownloadError, get_json, paginate_chembl, post_form_json
from app.data.sources.base import BaseSource, SourceUnavailable
from app.data.sources.sider import SiderSource

_MECHANISMS_FILE = "mechanisms.json"
_TARGETS_FILE = "targets.json"
_PUBCHEM_MAP_FILE = "pubchem_chembl_map.json"
_TARGET_BATCH = 40


class ChemblSource(BaseSource):
    source = Source.CHEMBL
    description = "ChEMBL mechanism-of-action + PubChem-CID/ChEMBL id map"
    license_note = "ChEMBL CC BY-SA 3.0; PubChem public domain."

    # pubchem map is best-effort (needs SIDER); only the two API pulls are required
    _required = (_MECHANISMS_FILE, _TARGETS_FILE)

    # -- download ------------------------------------------------------
    def download(self, *, force: bool = False) -> None:
        self.paths.raw_source_dir(self.source, create=True)
        mechanisms = self._download_mechanisms(force=force)
        self._download_targets(mechanisms, force=force)
        self._download_pubchem_map(force=force)

    def _download_mechanisms(self, *, force: bool) -> list[dict]:
        path = self.raw_dir / _MECHANISMS_FILE
        if not force and path.exists():
            return json.loads(path.read_text())
        try:
            mechanisms = list(
                paginate_chembl(
                    f"{CHEMBL_API_BASE}/mechanism.json", {"limit": 1000}, "mechanisms"
                )
            )
        except DownloadError as exc:
            raise SourceUnavailable(f"ChEMBL mechanism fetch failed: {exc}") from exc
        path.write_text(json.dumps(mechanisms))
        return mechanisms

    def _download_targets(self, mechanisms: list[dict], *, force: bool) -> None:
        path = self.raw_dir / _TARGETS_FILE
        if not force and path.exists():
            return
        target_ids = sorted(
            {m["target_chembl_id"] for m in mechanisms if m.get("target_chembl_id")}
        )
        targets: list[dict] = []
        for i in range(0, len(target_ids), _TARGET_BATCH):
            batch = target_ids[i : i + _TARGET_BATCH]
            try:
                page = get_json(
                    f"{CHEMBL_API_BASE}/target.json",
                    params={"target_chembl_id__in": ",".join(batch), "limit": 1000},
                )
            except DownloadError as exc:
                raise SourceUnavailable(f"ChEMBL target fetch failed: {exc}") from exc
            targets.extend(page.get("targets", []))
        path.write_text(json.dumps(targets))

    def _sider_cids(self) -> list[str]:
        sider = SiderSource(self.paths)
        if not sider.available():
            return []
        cids = {
            idn.normalize_pubchem_cid(s)
            for s in sider.extract_drugs()["stitch_id"].tolist()
        }
        return sorted(c for c in cids if c)

    def _download_pubchem_map(self, *, force: bool) -> None:
        """Best-effort: never lets a slow PubChem endpoint block the pipeline."""
        path = self.raw_dir / _PUBCHEM_MAP_FILE
        if not force and path.exists():
            return
        cids = self._sider_cids()
        if not cids:
            return  # SIDER not available yet; drug<->chembl linking will be skipped

        url = f"{PUBCHEM_PUG_REST}/compound/cid/synonyms/JSON"
        mapping: dict[str, str] = {}
        for i in range(0, len(cids), PUBCHEM_CID_BATCH):
            batch = cids[i : i + PUBCHEM_CID_BATCH]
            try:
                payload = post_form_json(
                    url, {"cid": ",".join(batch)}, retries=2, timeout=45.0
                )
            except DownloadError:
                continue  # skip this batch, keep going
            for info in payload.get("InformationList", {}).get("Information", []):
                cid = str(info.get("CID"))
                for syn in info.get("Synonym", []):
                    if syn.startswith("CHEMBL"):
                        mapping[cid] = syn
                        break
            time.sleep(0.2)  # PUG-REST rate etiquette
        path.write_text(json.dumps(mapping))

    # -- availability -------------------------------------------------
    def available(self) -> bool:
        return all((self.raw_dir / n).exists() for n in self._required)

    # -- parsing ---------------------------------------------------------
    def extract_chembl_pubchem(self) -> pd.DataFrame:
        self.ensure_available()
        path = self.raw_dir / _PUBCHEM_MAP_FILE
        if not path.exists():
            return pd.DataFrame(columns=["chembl_id", "pubchem_cid"])
        mapping = json.loads(path.read_text())
        return pd.DataFrame(
            [{"chembl_id": v, "pubchem_cid": k} for k, v in mapping.items()],
            columns=["chembl_id", "pubchem_cid"],
        )

    def extract_mechanisms(self) -> pd.DataFrame:
        self.ensure_available()
        data = json.loads((self.raw_dir / _MECHANISMS_FILE).read_text())
        df = pd.DataFrame(
            [
                {
                    "chembl_id": m.get("molecule_chembl_id"),
                    "target_chembl_id": m.get("target_chembl_id"),
                    "action_type": m.get("action_type"),
                    "mechanism_of_action": m.get("mechanism_of_action"),
                }
                for m in data
            ],
            columns=["chembl_id", "target_chembl_id", "action_type", "mechanism_of_action"],
        )
        return df.dropna(subset=["chembl_id", "target_chembl_id"])

    def extract_targets(self) -> pd.DataFrame:
        self.ensure_available()
        data = json.loads((self.raw_dir / _TARGETS_FILE).read_text())
        rows = []
        for t in data:
            components = t.get("target_components") or []
            accession = None
            gene_symbol = None
            for comp in components:
                accession = accession or comp.get("accession")
                for syn in comp.get("target_component_synonyms") or []:
                    if syn.get("syn_type") == "GENE_SYMBOL" and not gene_symbol:
                        gene_symbol = syn.get("component_synonym")
            rows.append(
                {
                    "target_chembl_id": t.get("target_chembl_id"),
                    "target_name": t.get("pref_name"),
                    "target_type": t.get("target_type"),
                    "uniprot_id": accession,
                    "gene_symbol": gene_symbol,
                }
            )
        return pd.DataFrame(
            rows,
            columns=[
                "target_chembl_id",
                "target_name",
                "target_type",
                "uniprot_id",
                "gene_symbol",
            ],
        ).dropna(subset=["target_chembl_id"])
