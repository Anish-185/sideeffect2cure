"""Reverse indexes for efficient candidate generation.

Built once from the Level 1 ``drug_targets`` dataset + the HGNC bridge + the
Level 3 Reactome index, so generation is dict lookups keyed by the disease's
genes / pathways rather than a scan of 1,430 drugs.

    hgnc_id      -> [drug target rows]        (gene-target route)
    reactome_id  -> {drug_id}                 (pathway route)
    drug_id      -> {reactome_id: meta}       (to fill the match record)
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field

import pandas as pd

from app.data.constants import Dataset
from app.data.loaders import load_dataset
from app.services.candidates.bridge import HGNCBridge, HGNCBridgeUnavailable, get_hgnc_bridge
from app.services.drug.enrichment import (
    PathwayEnrichmentUnavailable,
    ReactomeUniProtIndex,
    get_reactome_index,
)
from app.services.drug.repository import DrugRepository
from app.services.drug.repository import default_repository as drug_repository


@dataclass
class CandidateIndex:
    drug_repo: DrugRepository

    # gene-target route
    bridge: HGNCBridge | None = field(default=None, repr=False)
    hgnc_to_targets: dict[str, list[dict]] = field(default_factory=dict, repr=False)
    gene_target_available: bool = False
    gene_target_unavailable_reason: str | None = None
    hgnc_bridge_size: int = 0

    # pathway route
    reactome_to_drugs: dict[str, set[str]] = field(default_factory=dict, repr=False)
    drug_pathway_meta: dict[str, dict[str, dict]] = field(default_factory=dict, repr=False)
    pathway_available: bool = False
    pathway_unavailable_reason: str | None = None

    # coverage bookkeeping (for provenance / debugging, not scoring)
    target_rows: int = 0
    target_rows_bridged: int = 0
    drugs_with_pathways: int = 0

    # -- construction ------------------------------------------------
    @classmethod
    def build(
        cls,
        *,
        drug_repo: DrugRepository | None = None,
        hgnc_bridge: HGNCBridge | None = None,
        reactome_index: ReactomeUniProtIndex | None = None,
        drug_targets: pd.DataFrame | None = None,
    ) -> CandidateIndex:
        repo = drug_repo or drug_repository()
        dt = drug_targets if drug_targets is not None else load_dataset(Dataset.DRUG_TARGETS)
        idx = cls(drug_repo=repo)
        idx._build_gene_target(dt, hgnc_bridge)
        idx._build_pathway(dt, reactome_index)
        return idx

    def _build_gene_target(self, dt: pd.DataFrame, hgnc_bridge: HGNCBridge | None) -> None:
        bridge = hgnc_bridge
        if bridge is None:
            try:
                bridge = get_hgnc_bridge()
            except HGNCBridgeUnavailable as exc:
                self.gene_target_available = False
                self.gene_target_unavailable_reason = str(exc)
                return
        self.bridge = bridge
        self.hgnc_bridge_size = bridge.size

        rows = dt.dropna(subset=["uniprot_id"])
        self.target_rows = len(rows)
        for r in rows.itertuples(index=False):
            hgnc = bridge.hgnc_for_uniprot(getattr(r, "uniprot_id", None))
            if not hgnc:
                continue
            self.target_rows_bridged += 1
            self.hgnc_to_targets.setdefault(hgnc, []).append(
                {
                    "drug_id": str(r.drug_id),
                    "target_id": str(r.target_id),
                    "target_name": _s(getattr(r, "target_name", None)),
                    "uniprot_id": _s(getattr(r, "uniprot_id", None)),
                    "action_type": _s(getattr(r, "action_type", None)),
                    "source": _s(getattr(r, "source", None)) or "chembl",
                }
            )
        self.gene_target_available = True

    def _build_pathway(
        self, dt: pd.DataFrame, reactome_index: ReactomeUniProtIndex | None
    ) -> None:
        index = reactome_index
        if index is None:
            try:
                index = get_reactome_index()
            except PathwayEnrichmentUnavailable as exc:
                self.pathway_available = False
                self.pathway_unavailable_reason = str(exc)
                return

        by_drug = dt.dropna(subset=["uniprot_id"]).groupby("drug_id")["uniprot_id"].apply(list)
        for drug_id, uniprots in by_drug.items():
            pathways = index.pathways_for(list(uniprots), limit=None)
            if not pathways:
                continue
            self.drugs_with_pathways += 1
            meta: dict[str, dict] = {}
            for p in pathways:
                rid = p["reactome_id"]
                meta[rid] = {
                    "pathway_name": p.get("pathway_name"),
                    "supporting_target_count": p.get("supporting_target_count"),
                }
                self.reactome_to_drugs.setdefault(rid, set()).add(str(drug_id))
            self.drug_pathway_meta[str(drug_id)] = meta
        self.pathway_available = True

    # -- queries ----------------------------------------------------
    def targets_for_hgnc(self, hgnc_id: str) -> list[dict]:
        return self.hgnc_to_targets.get(hgnc_id, [])

    def drugs_for_reactome(self, reactome_id: str) -> set[str]:
        return self.reactome_to_drugs.get(reactome_id, set())

    def drug_pathway(self, drug_id: str, reactome_id: str) -> dict | None:
        return self.drug_pathway_meta.get(drug_id, {}).get(reactome_id)

    def drug_name(self, drug_id: str) -> str:
        rec = self.drug_repo.get_drug(drug_id)
        return rec["drug_name"] if rec else drug_id

    @property
    def universe_size(self) -> int:
        return len(self.drug_repo.drug_ids)


def _s(v: object) -> str | None:
    if v is None:
        return None
    try:
        if bool(pd.isna(v)):
            return None
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    return s or None


@functools.cache
def default_index() -> CandidateIndex:
    return CandidateIndex.build()


def reset_default_index() -> None:
    default_index.cache_clear()
