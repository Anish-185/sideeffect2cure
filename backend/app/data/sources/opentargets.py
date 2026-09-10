"""Open Targets Platform — disease -> gene (target) associations.

Source: https://platform.opentargets.org/  (GraphQL API v4)

Input scope is the ontology-id seed list in
``app/data/resources/disease_seed.tsv`` (tracked in git). For each id we fetch
the top ``OPENTARGETS_TARGETS_PER_DISEASE`` associated targets by overall
association score. Disease *names* and every score come from the API — nothing
is invented here.

License: Open Targets Platform data is released under CC0 1.0.
"""

from __future__ import annotations

import json

import pandas as pd

from app.data.constants import (
    DISEASE_SEED_FILE,
    OPENTARGETS_GRAPHQL_URL,
    OPENTARGETS_TARGETS_PER_DISEASE,
    Source,
)
from app.data.net import DownloadError, post_json
from app.data.sources.base import BaseSource, SourceUnavailable

_QUERY = """
query AssociatedTargets($id: String!, $size: Int!) {
  disease(efoId: $id) {
    id
    name
    associatedTargets(page: {index: 0, size: $size}) {
      count
      rows {
        score
        target { id approvedSymbol approvedName }
      }
    }
  }
}
"""


def load_disease_seed(path=DISEASE_SEED_FILE) -> list[str]:
    """Read the seed file: first whitespace-delimited token per non-comment line."""
    ids: list[str] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        ids.append(line.split()[0].strip())
    # de-duplicate, keep order
    seen: set[str] = set()
    return [i for i in ids if not (i in seen or seen.add(i))]


class OpenTargetsSource(BaseSource):
    source = Source.OPENTARGETS
    description = "Open Targets Platform disease-target associations"
    license_note = "CC0 1.0 (public domain)."

    def __init__(self, paths) -> None:
        super().__init__(paths)
        self.seed_ids = load_disease_seed()
        self.unresolved: list[str] = []

    def _cache_file(self, ontology_id: str):
        return self.raw_dir / f"{ontology_id.replace(':', '_')}.json"

    def download(self, *, force: bool = False) -> None:
        self.paths.raw_source_dir(self.source, create=True)
        errors: list[str] = []
        got = 0
        for oid in self.seed_ids:
            dest = self._cache_file(oid)
            if dest.exists() and not force:
                got += 1
                continue
            try:
                payload = post_json(
                    OPENTARGETS_GRAPHQL_URL,
                    {
                        "query": _QUERY,
                        "variables": {
                            "id": oid.replace(":", "_"),
                            "size": OPENTARGETS_TARGETS_PER_DISEASE,
                        },
                    },
                )
            except DownloadError as exc:
                errors.append(f"{oid}: {exc}")
                continue
            dest.write_text(json.dumps(payload))
            got += 1
        if got == 0:
            raise SourceUnavailable(
                "Open Targets: no disease responses retrieved. " + "; ".join(errors[:3])
            )

    def available(self) -> bool:
        return self.raw_dir.exists() and any(self.raw_dir.glob("*.json"))

    # -- parsing ---------------------------------------------------------
    def _iter_payloads(self):
        for f in sorted(self.raw_dir.glob("*.json")):
            try:
                yield json.loads(f.read_text())
            except json.JSONDecodeError:
                continue

    def extract_diseases(self) -> pd.DataFrame:
        self.ensure_available()
        rows = []
        self.unresolved = []
        for payload in self._iter_payloads():
            disease = (payload.get("data") or {}).get("disease")
            if not disease:
                continue
            rows.append({"ontology_id": disease["id"], "disease_name": disease["name"]})
        # record seed ids that resolved to nothing
        resolved = {r["ontology_id"] for r in rows}
        for oid in self.seed_ids:
            if oid.replace(":", "_") not in resolved:
                self.unresolved.append(oid)
        return pd.DataFrame(rows, columns=["ontology_id", "disease_name"]).drop_duplicates()

    def extract_disease_genes(self) -> pd.DataFrame:
        self.ensure_available()
        rows = []
        for payload in self._iter_payloads():
            disease = (payload.get("data") or {}).get("disease")
            if not disease:
                continue
            oid = disease["id"]
            assoc = (disease.get("associatedTargets") or {}).get("rows") or []
            for row in assoc:
                tgt = row.get("target") or {}
                rows.append(
                    {
                        "ontology_id": oid,
                        "ensembl_id": tgt.get("id"),
                        "gene_symbol": tgt.get("approvedSymbol"),
                        "gene_full_name": tgt.get("approvedName"),
                        "association_score": row.get("score"),
                    }
                )
        return pd.DataFrame(
            rows,
            columns=[
                "ontology_id",
                "ensembl_id",
                "gene_symbol",
                "gene_full_name",
                "association_score",
            ],
        )
