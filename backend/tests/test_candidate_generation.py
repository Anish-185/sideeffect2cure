"""Level 4 — candidate drug generation tests."""

from __future__ import annotations

import pytest

from app.models.candidate import (
    CandidateDrug,
    CandidateGenerationResult,
    GenerationMethod,
)
from app.services.candidates import (
    InvalidDiseaseProfileError,
    generate_candidates,
    generate_candidates_by_gene_target,
    generate_candidates_by_pathway,
)


# --- fixture-based (synthetic, deterministic) ---------------------
def test_gene_target_route(candidate_disease_profile, candidate_fixture_index):
    cands = generate_candidates_by_gene_target(
        candidate_disease_profile, index=candidate_fixture_index
    )
    assert [c.drug_id for c in cands] == ["DRUG:001"]
    c = cands[0]
    assert c.methods == [GenerationMethod.GENE_TARGET]
    gt = c.reasons[0].gene_target
    assert gt is not None
    assert gt.hgnc_id == "HGNC:1"
    assert gt.gene_symbol == "AAA"
    assert gt.disease_gene_ensembl_id == "ENSG000001"
    assert gt.drug_target_uniprot_id == "P0TEST1"
    assert gt.drug_action_type == "INHIBITOR"
    assert gt.disease_gene_source == "opentargets" and gt.drug_target_source == "chembl"


def test_pathway_route(candidate_disease_profile, candidate_fixture_index):
    cands = generate_candidates_by_pathway(
        candidate_disease_profile, index=candidate_fixture_index
    )
    assert [c.drug_id for c in cands] == ["DRUG:001"]
    pw = cands[0].reasons[0].pathway
    assert pw is not None
    assert pw.reactome_id == "R-HSA-TEST1"
    assert pw.disease_pathway_id == "PATH:C1"
    assert pw.disease_pathway_source == "derived:opentargets+reactome"
    assert pw.drug_pathway_source == "derived:chembl-targets+reactome"
    assert pw.disease_gene_support_count == 5
    assert pw.drug_supporting_target_count == 1


def test_union_dedups_drug_and_keeps_all_reasons(
    candidate_disease_profile, candidate_fixture_index
):
    res = generate_candidates(candidate_disease_profile, index=candidate_fixture_index)
    assert isinstance(res, CandidateGenerationResult)
    assert res.candidate_count == 1  # DRUG:001 via both routes, not duplicated
    c = res.candidates[0]
    assert set(c.methods) == {GenerationMethod.GENE_TARGET, GenerationMethod.PATHWAY}
    assert len(c.reasons) == 2
    assert {r.method for r in c.reasons} == {
        GenerationMethod.GENE_TARGET,
        GenerationMethod.PATHWAY,
    }


def test_convenience_rollups(candidate_disease_profile, candidate_fixture_index):
    res = generate_candidates(candidate_disease_profile, index=candidate_fixture_index)
    c = res.candidates[0]
    assert c.matched_gene_hgnc_ids == ["HGNC:1"]
    assert c.matched_gene_symbols == ["AAA"]
    assert c.matched_disease_gene_ids == ["GENE:C1"]
    assert c.matched_drug_target_ids == ["TGT:001"]
    assert c.matched_pathway_reactome_ids == ["R-HSA-TEST1"]


def test_counts_by_method(candidate_disease_profile, candidate_fixture_index):
    res = generate_candidates(candidate_disease_profile, index=candidate_fixture_index)
    m = res.counts_by_method
    assert m["gene_target"] == 1 and m["pathway"] == 1 and m["both"] == 1
    assert m["gene_target_only"] == 0 and m["pathway_only"] == 0
    assert m["universe"] == 3  # the drug fixture universe


def test_provenance_traceable_and_no_therapeutic_claim(
    candidate_disease_profile, candidate_fixture_index
):
    res = generate_candidates(candidate_disease_profile, index=candidate_fixture_index)
    prov = res.provenance
    assert prov.gene_target_bridge_available and prov.pathway_enrichment_available
    assert "hgnc_id" in prov.gene_target_bridge
    assert set(prov.methods_run) == {"gene_target", "pathway"}
    assert "not a therapeutic recommendation" in prov.interpretation_note.lower()
    assert "worth downstream" in prov.interpretation_note.lower()


def test_no_scoring_or_ranking_fields_anywhere():
    forbidden = {"score", "probability", "confidence", "rank", "ranking", "prediction",
                 "weight", "similarity", "repurposing_score"}
    for model in (CandidateDrug, CandidateGenerationResult):
        fields = set(model.model_fields)
        assert not (fields & forbidden), f"{model.__name__} has {fields & forbidden}"
    from app.models.candidate import CandidateGenerationReason, GeneTargetMatch, PathwayMatch

    for model in (CandidateGenerationReason, GeneTargetMatch, PathwayMatch):
        assert not (set(model.model_fields) & forbidden)


def test_empty_disease_profile_yields_zero_candidates_not_error(
    empty_disease_profile, candidate_fixture_index
):
    res = generate_candidates(empty_disease_profile, index=candidate_fixture_index)
    assert res.candidate_count == 0
    assert res.candidates == []
    assert res.disease_id == "DIS:E1"


def test_invalid_input_raises(candidate_fixture_index):
    for bad in (None, "glioblastoma", 42, {"disease_id": "x"}):
        with pytest.raises(InvalidDiseaseProfileError):
            generate_candidates(bad, index=candidate_fixture_index)  # type: ignore[arg-type]


def test_no_fabricated_relationships(candidate_disease_profile, candidate_fixture_index):
    """Every reason must reference ids that exist on the disease profile / index."""
    res = generate_candidates(candidate_disease_profile, index=candidate_fixture_index)
    disease_gene_ids = {g.gene_id for g in candidate_disease_profile.genes}
    disease_ensembl = {g.ensembl_id for g in candidate_disease_profile.genes}
    disease_reactome = {p.reactome_id for p in candidate_disease_profile.pathways}
    for c in res.candidates:
        for r in c.reasons:
            if r.gene_target:
                assert r.gene_target.disease_gene_id in disease_gene_ids
                assert r.gene_target.disease_gene_ensembl_id in disease_ensembl
                assert candidate_fixture_index.targets_for_hgnc(r.gene_target.hgnc_id)
            if r.pathway:
                assert r.pathway.reactome_id in disease_reactome
                assert c.drug_id in candidate_fixture_index.drugs_for_reactome(
                    r.pathway.reactome_id
                )


def test_gene_target_route_disabled_when_bridge_unavailable(
    candidate_disease_profile, drug_fixture_repo, drug_fixture_frames, fake_pathway_index
):
    from app.services.candidates import CandidateIndex

    idx = CandidateIndex(drug_repo=drug_fixture_repo)
    idx.gene_target_available = False
    idx.gene_target_unavailable_reason = "bridge file missing (test)"
    idx._build_pathway(drug_fixture_frames["drug_targets"], fake_pathway_index)

    res = generate_candidates(candidate_disease_profile, index=idx)
    assert res.provenance.gene_target_bridge_available is False
    assert "gene_target" not in res.provenance.methods_run
    # pathway route still produced the candidate
    assert res.candidate_count == 1
    assert res.candidates[0].methods == [GenerationMethod.PATHWAY]


# --- real Level 1/2 data ----------------------------------------
_GBM_KNOWN_TARGETS = {"EGFR", "ABL1", "KIT", "PDGFRB"}  # not exhaustive, not asserted as complete


def test_gbm_candidate_generation_mechanism(real_candidate_index):
    from app.services.disease import build_disease_profile

    profile = build_disease_profile("Glioblastoma")
    res = generate_candidates(profile, index=real_candidate_index)

    assert res.disease_id == profile.disease_id
    assert res.ontology_id == "MONDO_0018177"

    # a real, meaningful reduction of the 1,430-drug universe
    assert 0 < res.candidate_count < res.counts_by_method["universe"]

    # at least one route actually ran and produced candidates
    assert res.counts_by_method["gene_target"] > 0 or res.counts_by_method["pathway"] > 0

    # every candidate carries at least one concrete, real reason
    for c in res.candidates:
        assert c.reasons
        for r in c.reasons:
            assert (r.gene_target is not None) ^ (r.pathway is not None)
            if r.gene_target:
                assert r.gene_target.hgnc_id.startswith("HGNC:")
                assert r.gene_target.disease_gene_ensembl_id.startswith("ENSG")
                assert r.gene_target.drug_target_uniprot_id
            if r.pathway:
                assert r.pathway.reactome_id.startswith("R-")

    # gene-target reasons should surface known GBM druggable targets (mechanism check,
    # NOT a hardcoded candidate list)
    gt_symbols = {
        r.gene_target.gene_symbol
        for c in res.candidates
        for r in c.reasons
        if r.gene_target and r.gene_target.gene_symbol
    }
    assert gt_symbols & _GBM_KNOWN_TARGETS, gt_symbols


def test_gbm_union_is_superset_of_each_route(real_candidate_index):
    from app.services.disease import build_disease_profile

    profile = build_disease_profile("Glioblastoma")
    gt = {c.drug_id for c in generate_candidates_by_gene_target(profile, index=real_candidate_index)}
    pw = {c.drug_id for c in generate_candidates_by_pathway(profile, index=real_candidate_index)}
    union = {c.drug_id for c in generate_candidates(profile, index=real_candidate_index).candidates}
    assert union == gt | pw
    assert gt <= union and pw <= union


def test_two_diseases_give_different_candidate_sets(real_candidate_index):
    from app.services.disease import build_disease_profile

    gbm = generate_candidates(build_disease_profile("glioblastoma"), index=real_candidate_index)
    t2d = generate_candidates(
        build_disease_profile("type 2 diabetes mellitus"), index=real_candidate_index
    )
    gbm_ids = {c.drug_id for c in gbm.candidates}
    t2d_ids = {c.drug_id for c in t2d.candidates}
    assert gbm_ids != t2d_ids  # generation is disease-specific, not a fixed list
