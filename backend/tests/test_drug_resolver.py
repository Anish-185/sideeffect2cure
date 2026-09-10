"""Level 3 — DrugResolver tests."""

from __future__ import annotations

from app.models.drug import DrugMatchType, DrugResolutionStatus
from app.services.drug import DrugResolver, resolve_drug
from app.services.drug.repository import DrugRepository


# --- fixture repo (synthetic) -------------------------------------
def test_exact_name_resolution(drug_fixture_repo: DrugRepository):
    r = DrugResolver(drug_fixture_repo).resolve("test aspirin")
    assert r.status is DrugResolutionStatus.RESOLVED
    assert r.match.drug_id == "DRUG:001"
    assert r.match.matched_on is DrugMatchType.EXACT_NAME


def test_case_and_whitespace_insensitive(drug_fixture_repo: DrugRepository):
    for q in ["TEST ASPIRIN", "  Test   Aspirin ", "test aspirin."]:
        r = DrugResolver(drug_fixture_repo).resolve(q)
        assert r.status is DrugResolutionStatus.RESOLVED, q
        assert r.match.drug_id == "DRUG:001"


def test_internal_id_resolution(drug_fixture_repo: DrugRepository):
    r = DrugResolver(drug_fixture_repo).resolve("drug:001")
    assert r.status is DrugResolutionStatus.RESOLVED
    assert r.match.matched_on is DrugMatchType.INTERNAL_ID


def test_external_id_resolution(drug_fixture_repo: DrugRepository):
    for q in ["CHEMBL900001", "111", "CID:111", "CID111"]:
        r = DrugResolver(drug_fixture_repo).resolve(q)
        assert r.status is DrugResolutionStatus.RESOLVED, q
        assert r.match.drug_id == "DRUG:001"
        assert r.match.matched_on is DrugMatchType.EXTERNAL_ID


def test_unknown_drug_is_not_supported(drug_fixture_repo: DrugRepository):
    r = DrugResolver(drug_fixture_repo).resolve("imaginary compound zzz")
    assert r.status is DrugResolutionStatus.NOT_SUPPORTED
    assert r.match is None


def test_empty_query(drug_fixture_repo: DrugRepository):
    for q in ["", "   ", None]:
        r = DrugResolver(drug_fixture_repo).resolve(q)  # type: ignore[arg-type]
        assert r.status is DrugResolutionStatus.EMPTY_QUERY


def test_ambiguous_name_returns_candidates_not_a_guess(drug_fixture_repo: DrugRepository):
    r = DrugResolver(drug_fixture_repo).resolve("test salt")
    assert r.status is DrugResolutionStatus.AMBIGUOUS
    assert r.match is None
    assert {c.drug_id for c in r.candidates} == {"DRUG:002", "DRUG:003"}


def test_ambiguous_name_disambiguated_by_id(drug_fixture_repo: DrugRepository):
    r = DrugResolver(drug_fixture_repo).resolve("CHEMBL900003")
    assert r.status is DrugResolutionStatus.RESOLVED
    assert r.match.drug_id == "DRUG:003"


def test_invalid_ids(drug_fixture_repo: DrugRepository):
    for q in ["DRUG:999999", "CHEMBL999999", "CID:999999"]:
        r = DrugResolver(drug_fixture_repo).resolve(q)
        assert r.status is DrugResolutionStatus.NOT_SUPPORTED, q


def test_never_silently_returns_unrelated_drug(drug_fixture_repo: DrugRepository):
    r = DrugResolver(drug_fixture_repo).resolve("aspirin")  # not an exact fixture name
    assert r.status is DrugResolutionStatus.NOT_SUPPORTED
    assert r.match is None


# --- real Level 1 data ------------------------------------------
def test_aspirin_resolves_many_ways(real_drug_repo: DrugRepository):
    resolver = DrugResolver(real_drug_repo)
    for q in ["Aspirin", "aspirin", "  ASPIRIN ", "CHEMBL25", "2244", "CID:2244"]:
        r = resolver.resolve(q)
        assert r.status is DrugResolutionStatus.RESOLVED, q
        assert r.match.drug_name == "aspirin"
        assert r.match.chembl_id == "CHEMBL25"


def test_sider_salt_names_are_ambiguous(real_drug_repo: DrugRepository):
    # SIDER carries multiple compounds named "amlodipine" (salts) -> must not guess
    r = DrugResolver(real_drug_repo).resolve("amlodipine")
    assert r.status is DrugResolutionStatus.AMBIGUOUS
    assert len(r.candidates) >= 2


def test_module_level_resolve_drug(real_drug_repo: DrugRepository):
    r = resolve_drug("ibuprofen", repository=real_drug_repo)
    assert r.resolved and r.match.drug_name == "ibuprofen"
