"""Read-only, cached access to the Level 1 disease datasets, with the lookup
indexes the resolver needs.

Small by design: the disease tables are tiny (tens of diseases, a few thousand
association rows), so everything is loaded into memory once and indexed with
plain dicts. No database, no external cache.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from app.data.constants import DISEASE_SEED_FILE, Dataset
from app.data.loaders import load_dataset, load_identifier_map
from app.services.disease._normalize import normalize_disease_text, normalize_ontology

_ALIAS_FILE = DISEASE_SEED_FILE.parent / "disease_aliases.tsv"

# columns we require to be present and non-null for a row to be usable
_REQUIRED: dict[str, tuple[str, ...]] = {
    "diseases": ("disease_id", "disease_name"),
    "disease_genes": ("disease_id", "gene_id"),
    "disease_pathways": ("disease_id", "pathway_id", "pathway_name"),
}


@dataclass
class IntegrityIssue:
    dataset: str
    reason: str
    count: int


def _load_aliases(path: Path = _ALIAS_FILE) -> dict[str, str]:
    """alias (normalized) -> ontology id. File is optional."""
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        alias = normalize_disease_text(parts[0])
        onto = normalize_ontology(parts[1])
        if alias and onto:
            out[alias] = onto
    return out


@dataclass
class DiseaseRepository:
    diseases: pd.DataFrame
    disease_genes: pd.DataFrame
    disease_pathways: pd.DataFrame
    identifiers: pd.DataFrame
    integrity_issues: list[IntegrityIssue] = field(default_factory=list)

    # indexes (built in __post_init__)
    _by_id: dict[str, dict] = field(default_factory=dict, repr=False)
    _by_norm_name: dict[str, list[str]] = field(default_factory=dict, repr=False)
    _by_ontology: dict[str, list[str]] = field(default_factory=dict, repr=False)
    _by_alias: dict[str, list[str]] = field(default_factory=dict, repr=False)
    _unresolved_aliases: list[str] = field(default_factory=list, repr=False)

    # -- construction --------------------------------------------------
    @classmethod
    def from_loaders(cls) -> DiseaseRepository:
        return cls(
            diseases=load_dataset(Dataset.DISEASES),
            disease_genes=load_dataset(Dataset.DISEASE_GENES),
            disease_pathways=load_dataset(Dataset.DISEASE_PATHWAYS),
            identifiers=load_identifier_map(),
        )

    @classmethod
    def from_frames(
        cls,
        *,
        diseases: pd.DataFrame,
        disease_genes: pd.DataFrame,
        disease_pathways: pd.DataFrame,
        identifiers: pd.DataFrame | None = None,
    ) -> DiseaseRepository:
        return cls(
            diseases=diseases.copy(),
            disease_genes=disease_genes.copy(),
            disease_pathways=disease_pathways.copy(),
            identifiers=(identifiers.copy() if identifiers is not None else _empty_identifiers()),
        )

    def __post_init__(self) -> None:
        self._sanitize()
        self._build_indexes()

    # -- integrity ----------------------------------------------------
    def _sanitize(self) -> None:
        """Drop malformed rows deterministically; record what was dropped."""
        cleaned: dict[str, pd.DataFrame] = {}
        for name, df in (
            ("diseases", self.diseases),
            ("disease_genes", self.disease_genes),
            ("disease_pathways", self.disease_pathways),
        ):
            df = df.copy()
            for col in _REQUIRED[name]:
                if col not in df.columns:
                    df[col] = pd.NA
            before = len(df)
            mask_bad = df[list(_REQUIRED[name])].isna().any(axis=1)
            if "disease_id" in df.columns:
                mask_bad = mask_bad | (df["disease_id"].astype("string").str.strip() == "")
            n_bad = int(mask_bad.sum())
            if n_bad:
                self.integrity_issues.append(
                    IntegrityIssue(name, "missing required id/name", n_bad)
                )
            df = df[~mask_bad]
            # de-duplicate exact repeats
            n_dup = int(df.duplicated().sum())
            if n_dup:
                self.integrity_issues.append(IntegrityIssue(name, "exact duplicate row", n_dup))
                df = df.drop_duplicates()
            cleaned[name] = df.reset_index(drop=True)
            _ = before
        self.diseases = cleaned["diseases"]
        self.disease_genes = cleaned["disease_genes"]
        self.disease_pathways = cleaned["disease_pathways"]

        # referential integrity: association rows must point at a known disease
        known = set(self.diseases["disease_id"])
        for name in ("disease_genes", "disease_pathways"):
            df = getattr(self, name)
            orphan = ~df["disease_id"].isin(known)
            n_orphan = int(orphan.sum())
            if n_orphan:
                self.integrity_issues.append(
                    IntegrityIssue(name, "disease_id not in diseases", n_orphan)
                )
                setattr(self, name, df[~orphan].reset_index(drop=True))

    # -- indexes ----------------------------------------------------
    def _add_key(self, index: dict[str, list[str]], key: str, disease_id: str) -> None:
        if key:  # never index an empty normalized key
            index.setdefault(key, []).append(disease_id)

    def _build_indexes(self) -> None:
        for row in self.diseases.itertuples(index=False):
            did = str(row.disease_id)
            name = str(row.disease_name)
            onto = getattr(row, "ontology_id", None)
            onto = None if onto is None or pd.isna(onto) else str(onto)
            self._by_id[did] = {
                "disease_id": did,
                "disease_name": name,
                "ontology_id": onto,
                "source": str(getattr(row, "source", "") or ""),
            }
            self._add_key(self._by_norm_name, normalize_disease_text(name), did)
            if onto:
                self._add_key(self._by_ontology, normalize_ontology(onto), did)

        # crosswalk names + external ids also count as exact-name / ontology keys
        if not self.identifiers.empty:
            dis = self.identifiers[self.identifiers["entity_type"] == "disease"]
            for row in dis.itertuples(index=False):
                did = str(row.internal_id)
                if did not in self._by_id:
                    continue
                self._add_key(self._by_ontology, normalize_ontology(str(row.external_id)), did)
                nm = getattr(row, "name", None)
                if nm is not None and not pd.isna(nm):
                    self._add_key(self._by_norm_name, normalize_disease_text(str(nm)), did)

        # aliases: only keep those whose ontology target is actually ingested
        onto_to_id = {k: v for k, v in self._by_ontology.items()}
        for alias, onto in _load_aliases().items():
            targets = onto_to_id.get(normalize_ontology(onto))
            if targets:
                self._by_alias.setdefault(alias, []).extend(targets)
            else:
                self._unresolved_aliases.append(alias)

        # de-dupe every index's value lists, preserving order
        for idx in (self._by_norm_name, self._by_ontology, self._by_alias):
            for k, v in idx.items():
                idx[k] = list(dict.fromkeys(v))

    # -- queries ----------------------------------------------------
    @property
    def disease_ids(self) -> list[str]:
        return list(self._by_id)

    @property
    def unresolved_aliases(self) -> list[str]:
        return list(self._unresolved_aliases)

    def get_disease(self, disease_id: str) -> dict | None:
        return self._by_id.get(str(disease_id).strip().upper())

    def find_by_norm_name(self, norm: str) -> list[str]:
        return list(self._by_norm_name.get(norm, []))

    def find_by_ontology(self, norm: str) -> list[str]:
        return list(self._by_ontology.get(norm, []))

    def find_by_alias(self, norm: str) -> list[str]:
        return list(self._by_alias.get(norm, []))

    def name_suggestions(self, norm_query: str, limit: int = 5) -> list[str]:
        """Substring hints for NOT_SUPPORTED. Advisory only — never auto-selected."""
        if not norm_query:
            return []
        hits = [
            self._by_id[did]["disease_name"]
            for norm, ids in self._by_norm_name.items()
            for did in ids
            if norm_query in norm or norm in norm_query
        ]
        return list(dict.fromkeys(hits))[:limit]

    def genes_for(self, disease_id: str) -> pd.DataFrame:
        df = self.disease_genes[self.disease_genes["disease_id"] == disease_id]
        sort_cols = [c for c in ("association_score",) if c in df.columns]
        if sort_cols:
            df = df.sort_values(
                [*sort_cols, "gene_name"], ascending=[False, True], na_position="last"
            )
        return df.reset_index(drop=True)

    def pathways_for(self, disease_id: str) -> pd.DataFrame:
        df = self.disease_pathways[self.disease_pathways["disease_id"] == disease_id]
        by = [c for c in ("gene_support_count", "association_score") if c in df.columns]
        if by:
            df = df.sort_values(
                [*by, "pathway_name"],
                ascending=[False] * len(by) + [True],
                na_position="last",
            )
        return df.reset_index(drop=True)

    def external_identifiers_for(self, disease_id: str) -> list[dict]:
        if self.identifiers.empty:
            row = self._by_id.get(disease_id)
            if row and row.get("ontology_id"):
                return [
                    {"external_id": row["ontology_id"], "source": row["source"], "is_primary": True}
                ]
            return []
        sub = self.identifiers[
            (self.identifiers["entity_type"] == "disease")
            & (self.identifiers["internal_id"] == disease_id)
        ]
        return [
            {
                "external_id": str(r.external_id),
                "source": str(r.external_source),
                "is_primary": bool(getattr(r, "is_primary", False)),
            }
            for r in sub.itertuples(index=False)
        ]


def _empty_identifiers() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["internal_id", "entity_type", "external_id", "external_source", "name", "is_primary"]
    )


@functools.cache
def default_repository() -> DiseaseRepository:
    """Process-wide singleton built from the Level 1 loaders."""
    return DiseaseRepository.from_loaders()


def reset_default_repository() -> None:
    """Clear the cached singleton (used by tests / after re-ingestion)."""
    default_repository.cache_clear()
