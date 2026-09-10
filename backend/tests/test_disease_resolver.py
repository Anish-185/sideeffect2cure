"""Level 2 — DiseaseResolver tests."""

from __future__ import annotations

from app.models.disease import MatchType, ResolutionStatus
from app.services.disease import DiseaseResolver, resolve_disease
from app.services.disease.repository import DiseaseRepository


# --- fixture-repo (synthetic) --------------------------------------
def test_exact_name_resolution(fixture_repo: DiseaseRepository):
    r = DiseaseResolver(fixture_repo).resolve("sample carditis")
    assert r.status is ResolutionStatus.RESOLVED
    assert r.match.disease_id == "DIS:003"
    assert r.match.matched_on is MatchType.EXACT_NAME


def test_case_and_whitespace_insensitive(fixture_repo: DiseaseRepository):
    for q in ["SAMPLE CARDITIS", "  Sample   Carditis  ", "sample carditis."]:
        r = DiseaseResolver(fixture_repo).resolve(q)
        assert r.status is ResolutionStatus.RESOLVED, q
        assert r.match.disease_id == "DIS:003"


def test_internal_id_resolution(fixture_repo: DiseaseRepository):
    r = DiseaseResolver(fixture_repo).resolve("dis:003")
    assert r.status is ResolutionStatus.RESOLVED
    assert r.match.disease_id == "DIS:003"
    assert r.match.matched_on is MatchType.INTERNAL_ID


def test_ontology_id_resolution(fixture_repo: DiseaseRepository):
    for q in ["MONDO_9000003", "mondo:9000003"]:
        r = DiseaseResolver(fixture_repo).resolve(q)
        assert r.status is ResolutionStatus.RESOLVED, q
        assert r.match.disease_id == "DIS:003"
        assert r.match.matched_on is MatchType.ONTOLOGY_ID


def test_unknown_disease_is_not_supported(fixture_repo: DiseaseRepository):
    r = DiseaseResolver(fixture_repo).resolve("pineapple syndrome")
    assert r.status is ResolutionStatus.NOT_SUPPORTED
    assert r.match is None


def test_empty_query(fixture_repo: DiseaseRepository):
    for q in ["", "   ", None]:
        r = DiseaseResolver(fixture_repo).resolve(q)  # type: ignore[arg-type]
        assert r.status is ResolutionStatus.EMPTY_QUERY
        assert r.match is None


def test_ambiguous_name_returns_candidates_not_a_guess(fixture_repo: DiseaseRepository):
    r = DiseaseResolver(fixture_repo).resolve("test glioma")
    assert r.status is ResolutionStatus.AMBIGUOUS
    assert r.match is None
    assert {c.disease_id for c in r.candidates} == {"DIS:001", "DIS:002"}


def test_invalid_internal_id(fixture_repo: DiseaseRepository):
    r = DiseaseResolver(fixture_repo).resolve("DIS:123456")
    assert r.status is ResolutionStatus.NOT_SUPPORTED
    assert r.match is None


def test_invalid_ontology_id(fixture_repo: DiseaseRepository):
    r = DiseaseResolver(fixture_repo).resolve("MONDO_0000000")
    assert r.status is ResolutionStatus.NOT_SUPPORTED


def test_never_silently_returns_unrelated_disease(fixture_repo: DiseaseRepository):
    # a query that partially overlaps a real name must NOT resolve
    r = DiseaseResolver(fixture_repo).resolve("glioma")  # not an exact name / alias
    assert r.status is ResolutionStatus.NOT_SUPPORTED
    assert r.match is None


def test_alias_target_not_in_dataset_is_ignored(fixture_repo: DiseaseRepository):
    # the shipped alias file maps 'gbm' -> MONDO_0018177, absent from fixture data
    assert "gbm" not in fixture_repo._by_alias
    r = DiseaseResolver(fixture_repo).resolve("gbm")
    assert r.status is ResolutionStatus.NOT_SUPPORTED


# --- real Level 1 data --------------------------------------------
def test_gbm_resolves_by_name_id_and_alias(real_repo: DiseaseRepository):
    resolver = DiseaseResolver(real_repo)
    for q in ["Glioblastoma", "glioblastoma", "  GLIOBLASTOMA ", "GBM",
              "MONDO_0018177", "mondo:0018177"]:
        r = resolver.resolve(q)
        assert r.status is ResolutionStatus.RESOLVED, q
        assert r.match.ontology_id == "MONDO_0018177"
        assert r.match.disease_name == "glioblastoma"


def test_gbm_not_hardcoded_generic_resolution(real_repo: DiseaseRepository):
    # another disease must resolve by the same generic mechanism
    r = DiseaseResolver(real_repo).resolve("Parkinson disease")
    assert r.status is ResolutionStatus.RESOLVED
    assert r.match.ontology_id == "MONDO_0005180"


def test_module_level_resolve_disease_uses_real_data(real_repo: DiseaseRepository):
    r = resolve_disease("multiple sclerosis", repository=real_repo)
    assert r.resolved and r.match.ontology_id == "MONDO_0005301"
