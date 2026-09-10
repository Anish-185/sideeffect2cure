"""DrugResolver: user query -> exactly one supported drug, or an explicit
"cannot resolve" result.

Match order (first hit wins, all exact after normalization):

1. internal drug id     ``DRUG:000124``
2. external identifier   ``CHEMBL25`` / ``2244`` / ``CID:2244``
3. exact drug name       ``Aspirin`` -> ``aspirin``

No fuzzy / substring matching. Unmatched -> ``NOT_SUPPORTED`` (with advisory
name suggestions). SIDER contains multiple compounds under some shared names
(salts / stereoisomers), so a name query can be ``AMBIGUOUS`` -> the caller
must pick with an internal or external id.
"""

from __future__ import annotations

from app.models.drug import (
    DrugMatch,
    DrugMatchType,
    DrugResolutionResult,
    DrugResolutionStatus,
)
from app.services.drug._normalize import (
    as_chembl_id,
    as_pubchem_cid,
    looks_like_internal_id,
    normalize_drug_text,
    normalize_internal_id,
)
from app.services.drug.repository import DrugRepository, default_repository


class DrugResolver:
    def __init__(self, repository: DrugRepository | None = None) -> None:
        self.repo = repository or default_repository()

    def resolve(self, query: str) -> DrugResolutionResult:
        raw = "" if query is None else str(query)
        norm = normalize_drug_text(raw)

        if not raw.strip():
            return DrugResolutionResult(
                status=DrugResolutionStatus.EMPTY_QUERY,
                query=raw,
                normalized_query=norm,
                message="empty drug query",
            )

        for strategy in (self._match_internal_id, self._match_external_id, self._match_exact_name):
            result = strategy(raw, norm)
            if result is not None:
                return result

        return DrugResolutionResult(
            status=DrugResolutionStatus.NOT_SUPPORTED,
            query=raw,
            normalized_query=norm,
            suggestions=self.repo.name_suggestions(norm),
            message=(
                f"{raw!r} is not a supported drug. Supported drugs are the "
                f"{len(self.repo.drug_ids)} SIDER compounds ingested in Level 1."
            ),
        )

    # -- strategies ------------------------------------------------
    def _match_internal_id(self, raw: str, norm: str) -> DrugResolutionResult | None:
        if not looks_like_internal_id(raw):
            return None
        did = normalize_internal_id(raw)
        row = self.repo.get_drug(did)
        if row:
            return self._resolved(raw, norm, row, DrugMatchType.INTERNAL_ID, did)
        return DrugResolutionResult(
            status=DrugResolutionStatus.NOT_SUPPORTED,
            query=raw,
            normalized_query=norm,
            message=f"no drug with internal id {did}",
        )

    def _match_external_id(self, raw: str, norm: str) -> DrugResolutionResult | None:
        chembl = as_chembl_id(raw)
        cid = as_pubchem_cid(raw)
        if not chembl and not cid:
            return None
        for key in filter(None, (chembl, cid, f"CID:{cid}" if cid else None)):
            ids = self.repo.find_by_external(key)
            if ids:
                return self._one_or_ambiguous(raw, norm, ids, DrugMatchType.EXTERNAL_ID, key)
        return DrugResolutionResult(
            status=DrugResolutionStatus.NOT_SUPPORTED,
            query=raw,
            normalized_query=norm,
            message=f"external identifier {raw!r} is not among the ingested drugs",
        )

    def _match_exact_name(self, raw: str, norm: str) -> DrugResolutionResult | None:
        if not norm:
            return None
        ids = self.repo.find_by_norm_name(norm)
        if not ids:
            return None
        return self._one_or_ambiguous(raw, norm, ids, DrugMatchType.EXACT_NAME, norm)

    # -- helpers -------------------------------------------------
    def _one_or_ambiguous(
        self, raw: str, norm: str, ids: list[str], match_type: DrugMatchType, matched_value: str
    ) -> DrugResolutionResult:
        uniq = list(dict.fromkeys(ids))
        if len(uniq) == 1:
            return self._resolved(raw, norm, self.repo.get_drug(uniq[0]), match_type, matched_value)
        return DrugResolutionResult(
            status=DrugResolutionStatus.AMBIGUOUS,
            query=raw,
            normalized_query=norm,
            candidates=[self._match_obj(self.repo.get_drug(d), match_type, matched_value) for d in uniq],
            message=(
                f"{raw!r} matches {len(uniq)} drug records (SIDER salts/stereoisomers); "
                "disambiguate with an internal id (DRUG:...) or a ChEMBL / PubChem id"
            ),
        )

    @staticmethod
    def _match_obj(row: dict, match_type: DrugMatchType, matched_value: str) -> DrugMatch:
        return DrugMatch(
            drug_id=row["drug_id"],
            drug_name=row["drug_name"],
            chembl_id=row.get("chembl_id"),
            pubchem_cid=row.get("pubchem_cid"),
            matched_on=match_type,
            matched_value=matched_value,
        )

    def _resolved(
        self, raw: str, norm: str, row: dict, match_type: DrugMatchType, matched_value: str
    ) -> DrugResolutionResult:
        return DrugResolutionResult(
            status=DrugResolutionStatus.RESOLVED,
            query=raw,
            normalized_query=norm,
            match=self._match_obj(row, match_type, matched_value),
            message=f"resolved to {row['drug_id']} ({row['drug_name']})",
        )
