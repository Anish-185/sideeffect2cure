"""Identifier normalization and the internal-id registry.

Strategy (also documented in ``docs/data.md``):

* Every primary entity is keyed on a **normalized external identifier** — never
  on a name alone. Names are noisy; ids are not.

  =============  ===========================================================
  entity         normalized key
  =============  ===========================================================
  drug           PubChem CID (digits only). ChEMBL id kept as a secondary xref.
  disease        EFO / MONDO id, upper-cased, ``:`` -> ``_``.
  gene           Ensembl gene id (``ENSG...``), version suffix stripped.
  target         ChEMBL target id (``CHEMBL...``). UniProt kept as secondary.
  pathway        Reactome stable id (``R-HSA-...``).
  side effect    UMLS CUI (``C#######``).
  =============  ===========================================================

* ``IdRegistry`` mints a stable internal id (``DRUG:000123``) per normalized key
  on first sight and returns the same id thereafter. It also records every
  ``(internal_id, external_id, source)`` triple for the ``identifiers`` mapping
  table.

* Records whose normalized key cannot be derived are **not** silently dropped by
  this module — it raises / returns ``None`` and the caller logs the rejection.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pandas as pd

from app.data.constants import ID_PREFIXES, INTERNAL_ID_WIDTH, EntityType

# --- name normalization -------------------------------------------------
_WS_RE = re.compile(r"\s+")


def normalize_name(name: str | None) -> str | None:
    """Lower-case, collapse whitespace, strip. Returns ``None`` if empty."""
    if name is None:
        return None
    cleaned = _WS_RE.sub(" ", str(name)).strip().lower()
    return cleaned or None


# --- external-id normalization ----------------------------------------
def normalize_pubchem_cid(raw: str | int | None) -> str | None:
    """SIDER STITCH ids look like ``CID100000085`` / ``CID000010917``.

    The first digit after ``CID`` is a stereo (1) / flat (0) flag; the PubChem
    CID is the remaining digits with leading zeros removed.
    """
    if raw is None:
        return None
    s = str(raw).strip().upper()
    m = re.fullmatch(r"CID[01](\d+)", s)
    if m:
        return str(int(m.group(1)))
    if s.isdigit():
        return str(int(s))
    return None


def normalize_ontology_id(raw: str | None) -> str | None:
    """``EFO:0000305`` / ``MONDO_0018177`` -> ``EFO_0000305`` / ``MONDO_0018177``."""
    if raw is None:
        return None
    s = str(raw).strip().upper().replace(":", "_")
    return s or None


def normalize_ensembl_gene(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().upper()
    s = s.split(".", 1)[0]  # drop version suffix
    return s if s.startswith("ENSG") else None


def normalize_chembl_id(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().upper()
    return s if s.startswith("CHEMBL") else None


def normalize_reactome_id(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().upper()
    return s if s.startswith("R-") else None


def normalize_umls_cui(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().upper()
    return s if re.fullmatch(r"C\d{6,}", s) else None


def normalize_uniprot(raw: str | None) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().upper()
    ok = re.fullmatch(r"[OPQ][0-9][A-Z0-9]{3}[0-9]|[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}", s)
    return s if ok else None


# --- internal id registry --------------------------------------------
@dataclass
class _Namespace:
    prefix: str
    _by_key: dict[str, str] = field(default_factory=dict)
    _counter: int = 0

    def mint(self, key: str) -> str:
        existing = self._by_key.get(key)
        if existing is not None:
            return existing
        self._counter += 1
        internal = f"{self.prefix}:{self._counter:0{INTERNAL_ID_WIDTH}d}"
        self._by_key[key] = internal
        return internal

    def get(self, key: str) -> str | None:
        return self._by_key.get(key)


@dataclass
class MappingRecord:
    internal_id: str
    entity_type: str
    external_id: str
    external_source: str
    name: str | None
    is_primary: bool


class IdRegistry:
    """Mints internal ids and accumulates the identifier mapping table."""

    def __init__(self) -> None:
        self._ns: dict[EntityType, _Namespace] = {
            et: _Namespace(prefix=ID_PREFIXES[et]) for et in EntityType
        }
        self._mappings: dict[tuple[str, str, str], MappingRecord] = {}

    def resolve(
        self,
        entity_type: EntityType,
        primary_key: str,
        *,
        primary_source: str,
        name: str | None = None,
    ) -> str:
        """Return the internal id for ``primary_key``, minting it if new."""
        if not primary_key:
            raise ValueError(f"empty primary key for {entity_type}")
        internal = self._ns[entity_type].mint(primary_key)
        self.add_xref(
            internal,
            entity_type,
            external_id=primary_key,
            source=primary_source,
            name=name,
            is_primary=True,
        )
        return internal

    def lookup(self, entity_type: EntityType, primary_key: str) -> str | None:
        return self._ns[entity_type].get(primary_key)

    def add_xref(
        self,
        internal_id: str,
        entity_type: EntityType,
        *,
        external_id: str,
        source: str,
        name: str | None = None,
        is_primary: bool = False,
    ) -> None:
        if not external_id:
            return
        key = (internal_id, external_id, source)
        prev = self._mappings.get(key)
        if prev is None:
            self._mappings[key] = MappingRecord(
                internal_id=internal_id,
                entity_type=entity_type.value,
                external_id=external_id,
                external_source=source,
                name=name,
                is_primary=is_primary,
            )
        else:
            if name and not prev.name:
                prev.name = name
            prev.is_primary = prev.is_primary or is_primary

    def mapping_frame(self) -> pd.DataFrame:
        rows = [vars(r) for r in self._mappings.values()]
        df = pd.DataFrame(
            rows,
            columns=[
                "internal_id",
                "entity_type",
                "external_id",
                "external_source",
                "name",
                "is_primary",
            ],
        )
        if not df.empty:
            df = df.sort_values(["entity_type", "internal_id", "external_source"]).reset_index(
                drop=True
            )
        return df

    def counts(self) -> dict[str, int]:
        return {et.value: len(ns._by_key) for et, ns in self._ns.items()}
