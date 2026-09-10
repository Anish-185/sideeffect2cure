"""Read-only, cached access to the Level 1 drug datasets, with the lookup
indexes the resolver needs.

Reuses the Level 1 loaders and identifier crosswalk. No new ingestion, no
database. Everything is loaded once and indexed with plain dicts.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field

import pandas as pd

from app.data.constants import Dataset
from app.data.loaders import load_dataset, load_identifier_map
from app.services.drug._normalize import normalize_drug_text

_REQUIRED: dict[str, tuple[str, ...]] = {
    "drugs": ("drug_id", "drug_name"),
    "drug_side_effects": ("drug_id", "side_effect_id", "side_effect_name"),
    "drug_targets": ("drug_id", "target_id"),
}


@dataclass
class IntegrityIssue:
    dataset: str
    reason: str
    count: int


@dataclass
class DrugRepository:
    drugs: pd.DataFrame
    drug_side_effects: pd.DataFrame
    drug_targets: pd.DataFrame
    identifiers: pd.DataFrame
    integrity_issues: list[IntegrityIssue] = field(default_factory=list)

    _by_id: dict[str, dict] = field(default_factory=dict, repr=False)
    _by_norm_name: dict[str, list[str]] = field(default_factory=dict, repr=False)
    _by_external: dict[str, list[str]] = field(default_factory=dict, repr=False)

    # -- construction ------------------------------------------------
    @classmethod
    def from_loaders(cls) -> DrugRepository:
        return cls(
            drugs=load_dataset(Dataset.DRUGS),
            drug_side_effects=load_dataset(Dataset.DRUG_SIDE_EFFECTS),
            drug_targets=load_dataset(Dataset.DRUG_TARGETS),
            identifiers=load_identifier_map(),
        )

    @classmethod
    def from_frames(
        cls,
        *,
        drugs: pd.DataFrame,
        drug_side_effects: pd.DataFrame,
        drug_targets: pd.DataFrame,
        identifiers: pd.DataFrame | None = None,
    ) -> DrugRepository:
        return cls(
            drugs=drugs.copy(),
            drug_side_effects=drug_side_effects.copy(),
            drug_targets=drug_targets.copy(),
            identifiers=identifiers.copy() if identifiers is not None else _empty_identifiers(),
        )

    def __post_init__(self) -> None:
        self._sanitize()
        self._build_indexes()

    # -- integrity -------------------------------------------------
    def _sanitize(self) -> None:
        cleaned: dict[str, pd.DataFrame] = {}
        for name, df in (
            ("drugs", self.drugs),
            ("drug_side_effects", self.drug_side_effects),
            ("drug_targets", self.drug_targets),
        ):
            df = df.copy()
            for col in _REQUIRED[name]:
                if col not in df.columns:
                    df[col] = pd.NA
            bad = df[list(_REQUIRED[name])].isna().any(axis=1)
            if "drug_id" in df.columns:
                bad = bad | (df["drug_id"].astype("string").str.strip() == "")
            n_bad = int(bad.sum())
            if n_bad:
                self.integrity_issues.append(IntegrityIssue(name, "missing required id/name", n_bad))
            df = df[~bad]
            n_dup = int(df.duplicated().sum())
            if n_dup:
                self.integrity_issues.append(IntegrityIssue(name, "exact duplicate row", n_dup))
                df = df.drop_duplicates()
            cleaned[name] = df.reset_index(drop=True)
        self.drugs = cleaned["drugs"]
        self.drug_side_effects = cleaned["drug_side_effects"]
        self.drug_targets = cleaned["drug_targets"]

        known = set(self.drugs["drug_id"])
        for name in ("drug_side_effects", "drug_targets"):
            df = getattr(self, name)
            orphan = ~df["drug_id"].isin(known)
            n_orphan = int(orphan.sum())
            if n_orphan:
                self.integrity_issues.append(
                    IntegrityIssue(name, "drug_id not in drugs", n_orphan)
                )
                setattr(self, name, df[~orphan].reset_index(drop=True))

    # -- indexes -------------------------------------------------
    def _add_external(self, key: str | None, drug_id: str) -> None:
        if key:
            self._by_external.setdefault(str(key).strip().upper(), []).append(drug_id)

    def _build_indexes(self) -> None:
        for row in self.drugs.itertuples(index=False):
            did = str(row.drug_id)
            name = str(row.drug_name)
            rec = {
                "drug_id": did,
                "drug_name": name,
                "canonical_identifier": _val(getattr(row, "canonical_identifier", None)),
                "chembl_id": _val(getattr(row, "chembl_id", None)),
                "pubchem_cid": _val(getattr(row, "pubchem_cid", None)),
                "source": str(_val(getattr(row, "source", None)) or ""),
            }
            self._by_id[did] = rec
            self._by_norm_name.setdefault(normalize_drug_text(name), []).append(did)
            self._add_external(rec["chembl_id"], did)
            self._add_external(rec["canonical_identifier"], did)
            if rec["pubchem_cid"]:
                self._add_external(rec["pubchem_cid"], did)
                self._add_external(f"CID:{rec['pubchem_cid']}", did)

        if not self.identifiers.empty:
            dd = self.identifiers[self.identifiers["entity_type"] == "drug"]
            for row in dd.itertuples(index=False):
                did = str(row.internal_id)
                if did in self._by_id:
                    self._add_external(str(row.external_id), did)

        for idx in (self._by_norm_name, self._by_external):
            for k, v in idx.items():
                idx[k] = list(dict.fromkeys(v))

    # -- queries -------------------------------------------------
    @property
    def drug_ids(self) -> list[str]:
        return list(self._by_id)

    def get_drug(self, drug_id: str) -> dict | None:
        return self._by_id.get(str(drug_id).strip().upper())

    def find_by_norm_name(self, norm: str) -> list[str]:
        return list(self._by_norm_name.get(norm, []))

    def find_by_external(self, key: str) -> list[str]:
        return list(self._by_external.get(str(key).strip().upper(), []))

    def name_suggestions(self, norm_query: str, limit: int = 5) -> list[str]:
        if not norm_query:
            return []
        hits = [
            self._by_id[did]["drug_name"]
            for norm, ids in self._by_norm_name.items()
            for did in ids
            if norm_query in norm or norm in norm_query
        ]
        return list(dict.fromkeys(hits))[:limit]

    def side_effects_for(self, drug_id: str) -> pd.DataFrame:
        df = self.drug_side_effects[self.drug_side_effects["drug_id"] == drug_id]
        if "side_effect_name" in df.columns:
            df = df.sort_values("side_effect_name", na_position="last")
        return df.reset_index(drop=True)

    def targets_for(self, drug_id: str) -> pd.DataFrame:
        df = self.drug_targets[self.drug_targets["drug_id"] == drug_id]
        if "target_name" in df.columns:
            df = df.sort_values("target_name", na_position="last")
        return df.reset_index(drop=True)

    def external_identifiers_for(self, drug_id: str) -> list[dict]:
        if self.identifiers.empty:
            rec = self._by_id.get(drug_id, {})
            out = []
            for src, val in (("chembl", rec.get("chembl_id")), ("pubchem", rec.get("pubchem_cid"))):
                if val:
                    out.append({"external_id": val, "source": src, "is_primary": False})
            return out
        sub = self.identifiers[
            (self.identifiers["entity_type"] == "drug")
            & (self.identifiers["internal_id"] == drug_id)
        ]
        return [
            {
                "external_id": str(r.external_id),
                "source": str(r.external_source),
                "is_primary": bool(getattr(r, "is_primary", False)),
            }
            for r in sub.itertuples(index=False)
        ]


def _val(v: object) -> str | None:
    if v is None:
        return None
    try:
        if bool(pd.isna(v)):
            return None
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    return s or None


def _empty_identifiers() -> pd.DataFrame:
    return pd.DataFrame(
        columns=["internal_id", "entity_type", "external_id", "external_source", "name", "is_primary"]
    )


@functools.cache
def default_repository() -> DrugRepository:
    return DrugRepository.from_loaders()


def reset_default_repository() -> None:
    default_repository.cache_clear()
