"""Query normalization for the drug resolver."""

from __future__ import annotations

import re

from app.data.identifiers import normalize_name

_EDGE_PUNCT = re.compile(r"^[\s\"'`(\[{]+|[\s\"'`)\]}.,;:!?]+$")
_INTERNAL_DRUG_ID = re.compile(r"^DRUG:\d{1,9}$", re.IGNORECASE)
_CHEMBL_ID = re.compile(r"^CHEMBL\d+$", re.IGNORECASE)
_PUBCHEM_CID = re.compile(r"^(?:CID[:_]?)?(\d+)$", re.IGNORECASE)


def normalize_drug_text(query: str | None) -> str:
    """Lower-case, strip edge punctuation/quotes, collapse internal whitespace."""
    if query is None:
        return ""
    cleaned = _EDGE_PUNCT.sub("", str(query))
    cleaned = _EDGE_PUNCT.sub("", cleaned)
    return normalize_name(cleaned) or ""


def looks_like_internal_id(query: str) -> bool:
    return bool(_INTERNAL_DRUG_ID.match(query.strip()))


def normalize_internal_id(query: str) -> str:
    return query.strip().upper()


def as_chembl_id(query: str) -> str | None:
    q = query.strip().upper()
    return q if _CHEMBL_ID.match(q) else None


def as_pubchem_cid(query: str) -> str | None:
    """``2244`` / ``CID2244`` / ``CID:2244`` -> ``2244`` (leading zeros stripped)."""
    m = _PUBCHEM_CID.match(query.strip())
    if not m:
        return None
    return str(int(m.group(1)))
