"""Level 3 — DrugProfile construction tests."""

from __future__ import annotations

import pytest

from app.services.drug import (
    DrugResolutionError,
    UnknownDrugError,
    build_drug_profile,
    get_drug_profile,
)
from app.services.drug.repository import DrugRepository


# --- fixture repo -----------------------------------------------
def test_core_profile_construction(drug_fixture_repo: DrugRepository):
    p = get_drug_profile("DRUG:001", repository=drug_fixture_repo, enrich_pathways=False)
    assert p.drug_id == "DRUG:001"
    assert p.drug_name == "test aspirin"
    assert p.chembl_id == "CHEMBL900001"
    assert {s.side_effect_name for s in p.side_effects} == {"headache", "nausea"}
    assert p.side_effect_count == 2
    assert [t.target_name for t in p.targets] == ["Test Enzyme"]
    assert p.target_count == 1


def test_side_effect_fields_distinguishable(drug_fixture_repo: DrugRepository):
    p = get_drug_profile("DRUG:001", repository=drug_fixture_repo, enrich_pathways=False)
    se = next(s for s in p.side_effects if s.side_effect_name == "headache")
    assert se.side_effect_id == "SE:001"
    assert se.umls_cui == "C0000001"
    assert se.source == "sider"


def test_target_and_mechanism_fields(drug_fixture_repo: DrugRepository):
    p = get_drug_profile("DRUG:001", repository=drug_fixture_repo, enrich_pathways=False)
    t = p.targets[0]
    assert (t.target_id, t.action_type, t.uniprot_id, t.source) == (
        "TGT:001", "INHIBITOR", "P0TEST1", "chembl",
    )
    m = p.mechanisms[0]
    assert m.action_type == "INHIBITOR"
    assert m.description == "inhibitor of Test Enzyme"
    assert m.source == "chembl"


def test_provenance_is_preserved_and_labelled(drug_fixture_repo: DrugRepository):
    p = get_drug_profile("DRUG:001", repository=drug_fixture_repo, enrich_pathways=False)
    prov = p.provenance
    assert prov.side_effect_source.startswith("sider")
    assert prov.target_source.startswith("chembl")
    assert "SIDER" in prov.target_coverage_note and "not" in prov.target_coverage_note.lower()
    assert set(prov.optional_sources_skipped) == {"pubchem", "uniprot", "opentargets", "reactome"}
    assert "not evidence of clinical benefit" in p.summary_text


def test_unknown_drug_id_raises(drug_fixture_repo: DrugRepository):
    with pytest.raises(UnknownDrugError):
        get_drug_profile("DRUG:404", repository=drug_fixture_repo)


def test_build_from_query(drug_fixture_repo: DrugRepository):
    p = build_drug_profile("test aspirin", repository=drug_fixture_repo, enrich_pathways=False)
    assert p.drug_id == "DRUG:001"


def test_build_from_unresolvable_query_raises_with_result(drug_fixture_repo: DrugRepository):
    with pytest.raises(DrugResolutionError) as exc:
        build_drug_profile("nope nope", repository=drug_fixture_repo)
    assert exc.value.result.status.value == "not_supported"


def test_malformed_and_orphan_rows_dropped(drug_fixture_repo: DrugRepository):
    issues = {(i.dataset, i.reason): i.count for i in drug_fixture_repo.integrity_issues}
    assert issues[("drug_side_effects", "missing required id/name")] == 1
    assert issues[("drug_side_effects", "drug_id not in drugs")] == 1
    assert issues[("drug_targets", "drug_id not in drugs")] == 1
    p = get_drug_profile("DRUG:001", repository=drug_fixture_repo, enrich_pathways=False)
    assert "ghost" not in {s.side_effect_name for s in p.side_effects}


def test_optional_enrichment_can_be_unavailable_without_breaking_core(
    drug_fixture_repo: DrugRepository,
):
    p = get_drug_profile("DRUG:001", repository=drug_fixture_repo, enrich_pathways=False)
    bc = p.biological_context
    assert bc.pathway_context_available is False
    assert bc.unavailable_reason
    assert bc.proteins == ["P0TEST1"]          # protein list still populated
    assert p.side_effects and p.targets         # core intact


def test_optional_enrichment_with_injected_index(
    drug_fixture_repo: DrugRepository, fake_pathway_index
):
    p = get_drug_profile("DRUG:001", repository=drug_fixture_repo, pathway_index=fake_pathway_index)
    bc = p.biological_context
    assert bc.pathway_context_available is True
    assert [pw.pathway_name for pw in bc.pathways] == ["Test Pathway One"]
    assert bc.pathways[0].supporting_target_count == 1
    assert "reactome" in p.provenance.optional_sources_used


def test_drug_without_uniprot_target_has_no_pathways_but_core_ok(
    drug_fixture_repo: DrugRepository, fake_pathway_index
):
    p = get_drug_profile("DRUG:003", repository=drug_fixture_repo, pathway_index=fake_pathway_index)
    assert p.biological_context.proteins == []
    assert p.biological_context.pathway_context_available is False
    assert p.targets and p.mechanisms  # core still built


def test_no_fabricated_records(drug_fixture_repo: DrugRepository):
    p = get_drug_profile("DRUG:001", repository=drug_fixture_repo, enrich_pathways=False)
    src_se = drug_fixture_repo.side_effects_for("DRUG:001")
    src_t = drug_fixture_repo.targets_for("DRUG:001")
    assert {s.side_effect_id for s in p.side_effects} == set(src_se["side_effect_id"])
    assert {t.target_id for t in p.targets} == set(src_t["target_id"])


# --- real Level 1 data ------------------------------------------
def test_aspirin_profile_end_to_end(real_drug_repo: DrugRepository):
    p = build_drug_profile("Aspirin", repository=real_drug_repo, enrich_pathways=False)
    assert p.drug_id.startswith("DRUG:")
    assert p.drug_name == "aspirin"
    assert p.chembl_id == "CHEMBL25"
    assert p.pubchem_cid == "2244"

    assert p.side_effect_count > 0
    assert all(s.source == "sider" for s in p.side_effects)

    # aspirin's ChEMBL mechanism target is cyclooxygenase
    assert any("cyclooxygenase" in (t.target_name or "").lower() for t in p.targets)
    assert all(t.source == "chembl" for t in p.targets)
    assert any(m.action_type == "INHIBITOR" for m in p.mechanisms)

    # summary is deterministic + carries no therapeutic claims
    p2 = build_drug_profile("CHEMBL25", repository=real_drug_repo, enrich_pathways=False)
    assert p.summary_text == p2.summary_text
    for banned in ("cures", "treats", "therapeutically effective", "clinically effective"):
        assert banned not in p.summary_text.lower()
    assert "not evidence of clinical benefit" in p.summary_text


def test_real_side_effects_trace_to_dataset(real_drug_repo: DrugRepository):
    p = build_drug_profile("DRUG:000124", repository=real_drug_repo, enrich_pathways=False)
    raw = real_drug_repo.side_effects_for("DRUG:000124")
    assert {s.side_effect_id for s in p.side_effects} == set(raw["side_effect_id"])
    assert p.side_effect_count == len(raw)


@pytest.mark.slow
def test_aspirin_real_reactome_enrichment(real_drug_repo: DrugRepository):
    from app.services.drug.enrichment import PathwayEnrichmentUnavailable, get_reactome_index

    try:
        get_reactome_index()
    except PathwayEnrichmentUnavailable:
        pytest.skip("UniProt2Reactome not cached / unreachable")
    p = build_drug_profile("Aspirin", repository=real_drug_repo)
    bc = p.biological_context
    assert bc.pathway_context_available is True
    assert "P35354" in bc.proteins  # cyclooxygenase / PTGS2 accession
    names = " ".join(pw.pathway_name.lower() for pw in bc.pathways)
    assert "prostagland" in names or "thromboxane" in names
    assert all(pw.source == "derived:chembl-targets+reactome" for pw in bc.pathways)
