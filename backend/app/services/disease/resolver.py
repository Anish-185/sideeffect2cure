"""DiseaseResolver: user query -> exactly one supported disease, or an explicit
"cannot resolve" result.

Match order (first hit wins, all exact after normalization):

1. internal disease id      ``DIS:000035``
2. ontology id              ``MONDO_0018177`` / ``mondo:0018177``
3. exact disease name       ``Glioblastoma`` -> ``glioblastoma``
4. lexical alias            ``GBM`` -> ``glioblastoma`` (from disease_aliases.tsv)

No fuzzy / substring / "closest" matching — an unmatched query returns
``NOT_SUPPORTED`` (with advisory name suggestions), never a guessed disease.
Multiple distinct matches return ``AMBIGUOUS`` with the candidate list.
"""

from __future__ import annotations

from app.models.disease import (
    DiseaseMatch,
    MatchType,
    ResolutionResult,
    ResolutionStatus,
)
from app.services.disease._normalize import (
    looks_like_internal_id,
    looks_like_ontology_id,
    normalize_disease_text,
    normalize_internal_id,
    normalize_ontology,
)
from app.services.disease.repository import DiseaseRepository, default_repository


class DiseaseResolver:
    def __init__(self, repository: DiseaseRepository | None = None) -> None:
        self.repo = repository or default_repository()

    # -- public -------------------------------------------------------
    def resolve(self, query: str) -> ResolutionResult:
        raw = "" if query is None else str(query)
        norm = normalize_disease_text(raw)

        if not raw.strip():
            return ResolutionResult(
                status=ResolutionStatus.EMPTY_QUERY,
                query=raw,
                normalized_query=norm,
                message="empty disease query",
            )

        for strategy in (
            self._match_internal_id,
            self._match_ontology_id,
            self._match_exact_name,
            self._match_alias,
        ):
            result = strategy(raw, norm)
            if result is not None:
                return result

        return ResolutionResult(
            status=ResolutionStatus.NOT_SUPPORTED,
            query=raw,
            normalized_query=norm,
            suggestions=self.repo.name_suggestions(norm),
            message=(
                f"{raw!r} is not a supported disease. Supported diseases are limited to "
                f"the {len(self.repo.disease_ids)} ingested in Level 1."
            ),
        )

    # -- strategies -------------------------------------------------
    def _match_internal_id(self, raw: str, norm: str) -> ResolutionResult | None:
        if not looks_like_internal_id(raw):
            return None
        did = normalize_internal_id(raw)
        row = self.repo.get_disease(did)
        if row:
            return self._resolved(raw, norm, row, MatchType.INTERNAL_ID, did)
        return ResolutionResult(
            status=ResolutionStatus.NOT_SUPPORTED,
            query=raw,
            normalized_query=norm,
            message=f"no disease with internal id {did}",
        )

    def _match_ontology_id(self, raw: str, norm: str) -> ResolutionResult | None:
        if not looks_like_ontology_id(raw):
            return None
        key = normalize_ontology(raw)
        ids = self.repo.find_by_ontology(key)
        if not ids:
            return ResolutionResult(
                status=ResolutionStatus.NOT_SUPPORTED,
                query=raw,
                normalized_query=norm,
                message=f"ontology id {key} is not among the ingested diseases",
            )
        return self._one_or_ambiguous(raw, norm, ids, MatchType.ONTOLOGY_ID, key)

    def _match_exact_name(self, raw: str, norm: str) -> ResolutionResult | None:
        if not norm:
            return None
        ids = self.repo.find_by_norm_name(norm)
        if not ids:
            return None
        return self._one_or_ambiguous(raw, norm, ids, MatchType.EXACT_NAME, norm)

    def _match_alias(self, raw: str, norm: str) -> ResolutionResult | None:
        if not norm:
            return None
        ids = self.repo.find_by_alias(norm)
        if not ids:
            return None
        return self._one_or_ambiguous(raw, norm, ids, MatchType.ALIAS, norm)

    # -- helpers ---------------------------------------------------
    def _one_or_ambiguous(
        self, raw: str, norm: str, ids: list[str], match_type: MatchType, matched_value: str
    ) -> ResolutionResult:
        uniq = list(dict.fromkeys(ids))
        if len(uniq) == 1:
            return self._resolved(raw, norm, self.repo.get_disease(uniq[0]), match_type, matched_value)
        candidates = [
            self._match_obj(self.repo.get_disease(d), match_type, matched_value) for d in uniq
        ]
        return ResolutionResult(
            status=ResolutionStatus.AMBIGUOUS,
            query=raw,
            normalized_query=norm,
            candidates=candidates,
            message=f"{raw!r} matches {len(uniq)} diseases; disambiguate by internal or ontology id",
        )

    @staticmethod
    def _match_obj(row: dict, match_type: MatchType, matched_value: str) -> DiseaseMatch:
        return DiseaseMatch(
            disease_id=row["disease_id"],
            disease_name=row["disease_name"],
            ontology_id=row.get("ontology_id"),
            matched_on=match_type,
            matched_value=matched_value,
        )

    def _resolved(
        self, raw: str, norm: str, row: dict, match_type: MatchType, matched_value: str
    ) -> ResolutionResult:
        return ResolutionResult(
            status=ResolutionStatus.RESOLVED,
            query=raw,
            normalized_query=norm,
            match=self._match_obj(row, match_type, matched_value),
            message=f"resolved to {row['disease_id']} ({row['disease_name']})",
        )
