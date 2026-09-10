"""Query normalization shared by the resolver and repository indexes."""

from __future__ import annotations

import re

from app.data.identifiers import normalize_name, normalize_ontology_id

# strip surrounding quotes/brackets and trailing sentence punctuation
_EDGE_PUNCT = re.compile(r"^[\s\"'`(\[{]+|[\s\"'`)\]}.,;:!?]+$")
_INTERNAL_DISEASE_ID = re.compile(r"^DIS:\d{1,9}$", re.IGNORECASE)
_ONTOLOGY_ID = re.compile(r"^(EFO|MONDO|DOID|ORPHANET|ORDO|HP|NCIT|OMIM)[:_]\w+$", re.IGNORECASE)


def normalize_disease_text(query: str | None) -> str:
    """Lower-case, strip edge punctuation/quotes, collapse internal whitespace."""
    if query is None:
        return ""
    cleaned = _EDGE_PUNCT.sub("", str(query))
    cleaned = _EDGE_PUNCT.sub("", cleaned)  # second pass: e.g. "(x)." -> "x"
    return normalize_name(cleaned) or ""


def looks_like_internal_id(query: str) -> bool:
    return bool(_INTERNAL_DISEASE_ID.match(query.strip()))


def looks_like_ontology_id(query: str) -> bool:
    return bool(_ONTOLOGY_ID.match(query.strip()))


def normalize_internal_id(query: str) -> str:
    return query.strip().upper()


def normalize_ontology(query: str) -> str:
    return normalize_ontology_id(query) or ""
