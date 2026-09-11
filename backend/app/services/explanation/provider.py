"""``ExplanationProvider`` interface (Phase 9).

Any provider takes a ``RankedCandidate`` + its ``ExplanationContext`` and
returns a validated ``CandidateExplanation``, or raises
``ExplanationProviderError`` (or lets ``ExplanationValidationError`` from
validation propagate). Keeping this interface minimal is what lets the LLM
implementation (``DeepSeekFeatherlessProvider``) be replaced later without
touching ``service.py`` or anything upstream of it.
"""

from __future__ import annotations

from typing import Protocol

from app.models.explanation import CandidateExplanation, ExplanationContext
from app.models.ranking import RankedCandidate


class ExplanationProvider(Protocol):
    name: str

    def explain(
        self, candidate: RankedCandidate, context: ExplanationContext
    ) -> CandidateExplanation: ...
