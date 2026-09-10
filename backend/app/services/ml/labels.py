"""Supervised training target for Phase 6.

**We do not invent labels.** The label is a real, curated, *independent* signal:
whether a candidate drug has ever entered clinical development (any phase, incl.
approval) *for that disease*, per the Open Targets Platform
``disease.drugAndClinicalCandidates`` field (which aggregates ChEMBL drug
indications + ClinicalTrials.gov).

    label = 1  ->  the drug has a known clinical indication for this disease
    label = 0  ->  the drug has NO known clinical indication for this disease

This is **positive / unlabeled** weak supervision:

* a ``0`` means "not currently a known clinical drug for this disease" — it does
  **not** mean the drug is known to be ineffective (many ``0``s are exactly the
  repurposing hypotheses we care about);
* a ``1`` means the drug was *tried* (or approved), not that it *works* —
  ``drugAndClinicalCandidates`` includes failed trials.

The label is independent of Level 4 candidate generation (biology: target /
pathway overlap) and of every Level 5 feature — no leakage.

Responses are cached under ``data/raw/opentargets_known_drugs/`` (git-ignored,
regenerable). Free, public source.
"""

from __future__ import annotations

import functools
import json
from pathlib import Path

from app.core.config import get_settings
from app.data.constants import OPENTARGETS_GRAPHQL_URL
from app.data.net import DownloadError, post_json
from app.data.paths import DataPaths

_QUERY = (
    "query($id:String!){disease(efoId:$id){id name "
    "drugAndClinicalCandidates{count rows{drug{id} maxClinicalStage}}}}"
)


class LabelSourceUnavailable(RuntimeError):
    pass


def _cache_dir() -> Path:
    d = DataPaths.from_settings(get_settings()).raw / "opentargets_known_drugs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _cache_file(ontology_id: str) -> Path:
    return _cache_dir() / f"{ontology_id.replace(':', '_')}.json"


def fetch_known_drugs(ontology_id: str, *, force: bool = False) -> dict:
    """Return the raw cached payload for one disease, fetching + caching if needed."""
    oid = ontology_id.replace(":", "_")
    path = _cache_file(oid)
    if path.exists() and not force:
        return json.loads(path.read_text())
    try:
        payload = post_json(OPENTARGETS_GRAPHQL_URL, {"query": _QUERY, "variables": {"id": oid}})
    except DownloadError as exc:
        raise LabelSourceUnavailable(f"Open Targets query failed for {oid}: {exc}") from exc
    disease = (payload.get("data") or {}).get("disease")
    if disease is None:
        raise LabelSourceUnavailable(f"Open Targets returned no disease for {oid}")
    kd = disease.get("drugAndClinicalCandidates") or {}
    record = {
        "ontology_id": disease.get("id", oid),
        "name": disease.get("name"),
        "count": kd.get("count", 0),
        "chembl_ids": sorted(
            {r["drug"]["id"] for r in kd.get("rows", []) if r.get("drug", {}).get("id")}
        ),
        "max_clinical_stage": {
            r["drug"]["id"]: r.get("maxClinicalStage")
            for r in kd.get("rows", [])
            if r.get("drug", {}).get("id")
        },
    }
    path.write_text(json.dumps(record))
    return record


def known_chembl_ids(ontology_id: str, *, force: bool = False) -> set[str]:
    return set(fetch_known_drugs(ontology_id, force=force).get("chembl_ids", []))


@functools.cache
def _cached_known(ontology_id: str) -> frozenset[str]:
    return frozenset(known_chembl_ids(ontology_id))


def label_for(chembl_id: str | None, ontology_id: str) -> int:
    """1 if the drug is a known clinical candidate for the disease, else 0."""
    if not chembl_id:
        return 0
    return int(chembl_id in _cached_known(ontology_id))


def reset_label_cache() -> None:
    _cached_known.cache_clear()
