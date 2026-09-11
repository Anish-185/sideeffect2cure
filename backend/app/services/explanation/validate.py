"""Phase 9 response validation — grounding checks on the LLM's JSON payload.

Deliberately lightweight (no general NLP fact-checking): it checks the
structured fields the model was asked to echo, that any identifier it
mentions was actually supplied in the context, and that no banned
clinical-claim phrase appears. Any failure raises
``ExplanationValidationError`` so the caller falls back to the deterministic
provider — the response is never partially or silently accepted.

Only prose (``summary``, per-family ``evidence_notes``, ``limitations``) is
taken from the payload. Every structural field (``value``,
``contribution_points``, ``supporting_ids``, ids, rank, score) is rebuilt from
the same deterministic evidence the LLM was shown — the model cannot alter a
number even if it tried.
"""

from __future__ import annotations

import math
import re
from datetime import UTC, datetime

from app.core.config import DISCLAIMER
from app.models.explanation import (
    BiologicalEvidenceItem,
    CandidateExplanation,
    ExplanationContext,
    ExplanationProvenance,
)
from app.models.ranking import RankedCandidate
from app.services.explanation import descriptions as _d
from app.services.explanation.errors import ExplanationValidationError

_REQUIRED_KEYS = (
    "disease_id",
    "drug_id",
    "rank",
    "repurposing_score",
    "summary",
    "limitations",
)

# Whole-word/phrase matches (case-insensitive) — deliberately favours false
# positives (-> safe deterministic fallback) over letting a clinical claim
# through.
_BANNED_PHRASES = (
    "effective",
    "will treat",
    "treats",
    "cure",
    "cures",
    "curing",
    "treatment probability",
    "safe",
    "safely",
    "clinically proven",
    "proven",
    "guarantee",
    "guaranteed",
)

_ID_PATTERN = re.compile(r"\b(?:HGNC:\d+|TGT:\d+|GENE:\d+|DIS:\d+|DRUG:\d+|R-HSA-\d+)\b")


def _fail(reason: str) -> None:
    raise ExplanationValidationError(reason)


def _check_no_banned_language(*texts: str) -> None:
    for t in texts:
        for phrase in _BANNED_PHRASES:
            pattern = r"\b" + r"\s+".join(re.escape(w) for w in phrase.split()) + r"\b"
            if re.search(pattern, t, re.IGNORECASE):
                _fail(f"response used disallowed clinical-claim language: {phrase!r}")


def _check_identifiers(allowed: set[str], *texts: str) -> None:
    for t in texts:
        for match in _ID_PATTERN.findall(t):
            if match not in allowed:
                _fail(f"response referenced an identifier not present in the supplied evidence: {match!r}")


def validate_llm_payload(
    raw: object,
    candidate: RankedCandidate,
    context: ExplanationContext,
    *,
    provider_name: str,
    model_name: str,
) -> CandidateExplanation:
    """Validate ``raw`` (the parsed LLM JSON) against ``candidate``/``context``
    and, if it passes, build the final ``CandidateExplanation``.

    Raises ``ExplanationValidationError`` on the first failure.
    """
    if not isinstance(raw, dict):
        raise ExplanationValidationError("response was not a JSON object")

    missing = [k for k in _REQUIRED_KEYS if k not in raw]
    if missing:
        _fail(f"response missing required keys: {missing}")

    if str(raw["disease_id"]) != candidate.disease_id:
        _fail("response disease_id does not match the input candidate")
    if str(raw["drug_id"]) != candidate.drug_id:
        _fail("response drug_id does not match the input candidate")
    try:
        if int(raw["rank"]) != candidate.rank:
            _fail("response rank does not match the input candidate")
    except (TypeError, ValueError):
        _fail("response rank was not an integer")
    try:
        if not math.isclose(float(raw["repurposing_score"]), candidate.repurposing_score, abs_tol=0.05):
            _fail("response repurposing_score does not match the input candidate")
    except (TypeError, ValueError):
        _fail("response repurposing_score was not a number")

    summary = raw.get("summary")
    limitations = raw.get("limitations")
    notes = raw.get("evidence_notes") or {}
    if not isinstance(summary, str) or not summary.strip():
        _fail("response summary was empty or not a string")
    if not isinstance(limitations, list) or not all(isinstance(x, str) for x in limitations):
        _fail("response limitations was not a list of strings")
    if not isinstance(notes, dict):
        _fail("response evidence_notes was not an object")

    text_fields = [summary, *limitations, *(v for v in notes.values() if isinstance(v, str))]
    _check_no_banned_language(*text_fields)
    _check_identifiers(context.allowed_identifiers(), *text_fields)

    bio_items: list[BiologicalEvidenceItem] = []
    for item in _d.biological_evidence_items(candidate):
        note = notes.get(item.kind)
        description = note.strip() if isinstance(note, str) and note.strip() else item.description
        bio_items.append(item.model_copy(update={"description": description}))

    ml_note = notes.get("ml")
    model_evidence = _d.model_evidence_item(candidate)
    if isinstance(ml_note, str) and ml_note.strip():
        model_evidence = model_evidence.model_copy(update={"description": ml_note.strip()})

    clean_limitations = [x.strip() for x in limitations if isinstance(x, str) and x.strip()]

    return CandidateExplanation(
        disease_id=candidate.disease_id,
        drug_id=candidate.drug_id,
        disease_name=candidate.disease_name,
        drug_name=candidate.drug_name,
        rank=candidate.rank,
        repurposing_score=candidate.repurposing_score,
        summary=summary.strip(),
        biological_evidence=bio_items,
        model_evidence=model_evidence,
        limitations=clean_limitations or _d.deterministic_limitations(candidate),
        provenance=ExplanationProvenance(
            provider=provider_name,
            model_name=model_name,
            generated_at=datetime.now(UTC).isoformat(),
            scoring_version=context.scoring_version,
            ranking_version=context.ranking_version,
            validation_notes=["response passed grounding validation"],
            disclaimer=DISCLAIMER,
        ),
    )
