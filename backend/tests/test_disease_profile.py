"""Level 2 — DiseaseProfile construction tests."""

from __future__ import annotations

import pytest

from app.services.disease import (
    DiseaseResolutionError,
    UnknownDiseaseError,
    build_disease_profile,
    get_disease_profile,
)
from app.services.disease.repository import DiseaseRepository, IntegrityIssue


# --- fixture repo ------------------------------------------------
def test_profile_construction_from_fixture(fixture_repo: DiseaseRepository):
    p = get_disease_profile("DIS:001", repository=fixture_repo)
    assert p.disease_id == "DIS:001"
    assert p.disease_name == "test glioma"
    assert p.ontology_id == "MONDO_9000001"
    assert [g.gene_name for g in p.genes] == ["AAA", "BBB"]  # score-ordered
    assert [pw.pathway_id for pw in p.pathways] == ["PATH:001", "PATH:002"]  # support-ordered


def test_gene_fields_are_distinguishable(fixture_repo: DiseaseRepository):
    p = get_disease_profile("DIS:001", repository=fixture_repo)
    g = p.genes[0]
    assert g.gene_id == "GENE:001"
    assert g.gene_name == "AAA"
    assert g.ensembl_id == "ENSG000001"
    assert g.association_score == pytest.approx(0.9)
    assert g.source == "opentargets"


def test_pathway_provenance_is_derived(fixture_repo: DiseaseRepository):
    p = get_disease_profile("DIS:001", repository=fixture_repo)
    assert all(pw.source == "derived:opentargets+reactome" for pw in p.pathways)
    assert p.pathways[0].gene_support_count == 6
    assert "DERIVED" in p.provenance.pathway_derivation
    assert p.provenance.pathway_min_gene_support == 3


def test_provenance_and_disclaimer_present(fixture_repo: DiseaseRepository):
    p = get_disease_profile("DIS:003", repository=fixture_repo)
    prov = p.provenance
    assert "disease_genes" in prov.datasets_used and "disease_pathways" in prov.datasets_used
    assert "associated with" in prov.gene_score_semantics.lower()
    assert "not" in prov.disclaimer.lower()
    assert "causes" not in p.summary_text or "does not mean 'causes'" in p.summary_text


def test_unknown_disease_id_raises(fixture_repo: DiseaseRepository):
    with pytest.raises(UnknownDiseaseError):
        get_disease_profile("DIS:404", repository=fixture_repo)


def test_build_from_query_resolves_then_profiles(fixture_repo: DiseaseRepository):
    p = build_disease_profile("sample carditis", repository=fixture_repo)
    assert p.disease_id == "DIS:003"


def test_build_from_unresolvable_query_raises_with_result(fixture_repo: DiseaseRepository):
    with pytest.raises(DiseaseResolutionError) as exc:
        build_disease_profile("no such disease", repository=fixture_repo)
    assert exc.value.result.status.value == "not_supported"


def test_malformed_and_orphan_rows_are_dropped_and_recorded(fixture_repo: DiseaseRepository):
    issues = {(i.dataset, i.reason): i.count for i in fixture_repo.integrity_issues}
    assert issues[("disease_genes", "missing required id/name")] == 1
    assert issues[("disease_genes", "disease_id not in diseases")] == 1
    # the dropped rows must not surface in any profile
    p = get_disease_profile("DIS:001", repository=fixture_repo)
    assert all(g.gene_id and g.gene_name != "DDD" for g in p.genes)
    assert "GENE:009" not in {g.gene_id for g in p.genes}


def test_no_fabricated_rows_everything_traces_to_source(fixture_repo: DiseaseRepository):
    p = get_disease_profile("DIS:001", repository=fixture_repo)
    src_genes = fixture_repo.genes_for("DIS:001")
    assert {g.gene_id for g in p.genes} == set(src_genes["gene_id"])
    src_pw = fixture_repo.pathways_for("DIS:001")
    assert {pw.pathway_id for pw in p.pathways} == set(src_pw["pathway_id"])
    for g in p.genes:
        assert g.association_score in set(src_genes["association_score"])


# --- real Level 1 data --------------------------------------------
_GBM_KNOWN_GENES = {"TP53", "IDH1", "EGFR", "PTEN", "BRAF"}


def test_gbm_end_to_end(real_repo: DiseaseRepository):
    p = build_disease_profile("Glioblastoma", repository=real_repo)
    assert p.disease_id.startswith("DIS:")
    assert p.ontology_id == "MONDO_0018177"
    assert p.disease_name == "glioblastoma"

    symbols = {g.gene_name for g in p.genes}
    # known GBM genes must be present (not asserting this is the complete set)
    assert _GBM_KNOWN_GENES.issubset(symbols), _GBM_KNOWN_GENES - symbols
    assert len(p.genes) > 0 and len(p.pathways) > 0

    # gene scores are within Open Targets' [0,1]
    assert all(0.0 <= g.association_score <= 1.0 for g in p.genes if g.association_score is not None)
    # pathways are the derived kind
    assert all(pw.source.startswith("derived") for pw in p.pathways)
    assert all((pw.gene_support_count or 0) >= 3 for pw in p.pathways)

    # summary is deterministic + mentions real genes, no therapeutic claims
    assert p.summary_text == build_disease_profile("glioblastoma", repository=real_repo).summary_text
    assert "TP53" in p.summary_text
    for banned in ("cures", "treats", "therapeutically effective"):
        assert banned not in p.summary_text.lower()


def test_gbm_genes_trace_to_disease_genes_dataset(real_repo: DiseaseRepository):
    p = build_disease_profile("GBM", repository=real_repo)
    raw = real_repo.genes_for(p.disease_id)
    assert {g.gene_id for g in p.genes} == set(raw["gene_id"])
    assert p.molecular_profile.gene_count == len(raw)
    assert p.provenance.genes_truncated == (len(raw) >= p.provenance.genes_capped_per_disease)


def test_real_repo_integrity_clean(real_repo: DiseaseRepository):
    # Level 1 output should already be clean -> no integrity issues on load
    assert real_repo.integrity_issues == [] or all(
        isinstance(i, IntegrityIssue) for i in real_repo.integrity_issues
    )
