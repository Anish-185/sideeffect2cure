"""Level 5 — feature engineering tests."""

from __future__ import annotations

import math

import pytest

from app.models.candidate import CandidateDrug
from app.models.feature import FeatureVector, FeatureVectorMetadata
from app.services.features import (
    InvalidFeatureInputError,
    build_feature_vector,
    build_feature_vectors,
    feature_rows,
)


# --- fixture-based (synthetic, deterministic) --------------------
def test_basic_construction(feature_inputs):
    v = build_feature_vector(
        feature_inputs["candidate"],
        feature_inputs["disease_profile"],
        feature_inputs["drug_profile"],
        index=feature_inputs["index"],
    )
    assert isinstance(v, FeatureVector)
    assert v.disease_id == "DIS:C1"
    assert v.drug_id == "DRUG:001"
    assert v.drug_name == "test aspirin"
    assert isinstance(v.metadata, FeatureVectorMetadata)


def test_candidate_generation_features(feature_inputs):
    v = build_feature_vector(**_kw(feature_inputs))
    assert v.generated_by_gene_target is True
    assert v.generated_by_pathway is True
    assert v.generation_method_count == 2
    assert v.gene_target_reason_count == 1
    assert v.pathway_reason_count == 1


def test_gene_target_overlap_features(feature_inputs):
    v = build_feature_vector(**_kw(feature_inputs))
    assert v.disease_gene_count == 2
    assert v.disease_gene_hgnc_mapped_count == 2          # ENSG000001, ENSG000002
    assert v.drug_target_count == 1
    assert v.drug_target_hgnc_mapped_count == 1           # P0TEST1 -> HGNC:1
    assert v.matched_gene_target_count == 1              # HGNC:1 shared
    assert v.matched_disease_gene_count == 1
    assert v.matched_drug_target_count == 1
    assert v.fraction_of_drug_targets_matching_disease_genes == 1.0     # 1/1
    assert v.fraction_of_disease_genes_targeted_by_drug == 0.5         # 1/2


def test_pathway_overlap_features(feature_inputs):
    v = build_feature_vector(**_kw(feature_inputs))
    assert v.disease_pathway_count == 2                  # R-HSA-TEST1, R-HSA-NOPE
    assert v.drug_pathway_count == 1                     # R-HSA-TEST1
    assert v.matched_pathway_count == 1
    assert v.fraction_of_drug_pathways_matching_disease_pathways == 1.0    # 1/1
    assert v.fraction_of_disease_pathways_matching_drug_pathways == 0.5   # 1/2


def test_side_effect_and_target_and_drug_level_features(feature_inputs):
    v = build_feature_vector(**_kw(feature_inputs))
    assert v.side_effect_count == 2
    assert v.unique_target_count == 1
    assert v.inhibitor_target_count == 1
    assert v.agonist_target_count == 0
    assert v.antagonist_target_count == 0
    assert v.targets_missing_action_type_count == 0
    assert v.target_action_type_counts == {"INHIBITOR": 1}
    assert v.target_type_counts == {"SINGLE PROTEIN": 1}
    assert v.mechanism_count == 1


def test_evidence_availability_flags(feature_inputs):
    v = build_feature_vector(**_kw(feature_inputs))
    assert v.has_sider_evidence is True
    assert v.has_chembl_target_evidence is True
    assert v.has_reactome_pathway_evidence is True
    assert v.has_gene_target_bridge is True
    assert v.disease_pathways_available is True
    assert v.metadata.unavailable == []


def test_zero_denominator_yields_none_not_error(
    empty_disease_profile, candidate_fixture_index, drug_fixture_repo
):
    """A disease with no genes / pathways -> ratios are None, never NaN / crash."""
    from app.services.drug import get_drug_profile

    cand = CandidateDrug(
        drug_id="DRUG:001", drug_name="test aspirin",
        disease_id="DIS:E1", disease_name="empty disease",
        methods=[], reasons=[],
    )
    dp = get_drug_profile("DRUG:001", repository=drug_fixture_repo, enrich_pathways=False)
    v = build_feature_vector(cand, empty_disease_profile, dp, index=candidate_fixture_index)
    assert v.disease_gene_count == 0
    assert v.disease_gene_hgnc_mapped_count == 0
    assert v.fraction_of_disease_genes_targeted_by_drug is None
    assert v.fraction_of_disease_pathways_matching_drug_pathways is None
    assert v.matched_gene_target_count == 0
    assert v.disease_pathways_available is False


def test_missing_pathway_context_degrades_gracefully(
    candidate_disease_profile, drug_fixture_repo, drug_fixture_frames
):
    from app.services.candidates import CandidateIndex, generate_candidates
    from app.services.candidates.bridge import HGNCBridge
    from app.services.drug import get_drug_profile

    bridge = HGNCBridge(
        ensembl_to_hgnc={"ENSG000001": "HGNC:1", "ENSG000002": "HGNC:2"},
        uniprot_to_hgnc={"P0TEST1": "HGNC:1"},
        hgnc_to_symbol={"HGNC:1": "AAA", "HGNC:2": "BBB"},
    )
    idx = CandidateIndex(drug_repo=drug_fixture_repo)
    idx._build_gene_target(drug_fixture_frames["drug_targets"], bridge)
    idx.pathway_available = False
    idx.pathway_unavailable_reason = "reactome file missing (test)"

    res = generate_candidates(candidate_disease_profile, index=idx)
    cand = next(c for c in res.candidates if c.drug_id == "DRUG:001")  # via gene-target only
    dp = get_drug_profile("DRUG:001", repository=drug_fixture_repo, enrich_pathways=False)

    v = build_feature_vector(cand, candidate_disease_profile, dp, index=idx)
    assert v.has_gene_target_bridge is True
    assert v.matched_gene_target_count == 1               # gene-target still works
    assert v.drug_pathway_count == 0
    assert v.matched_pathway_count == 0
    assert v.fraction_of_drug_pathways_matching_disease_pathways is None
    assert v.has_reactome_pathway_evidence is False
    assert "reactome_pathway" in v.metadata.unavailable
    assert v.metadata.drug_pathway_source == "unavailable"


def test_missing_gene_target_bridge_degrades_gracefully(
    candidate_disease_profile, drug_fixture_repo, drug_fixture_frames, fake_pathway_index
):
    from app.services.candidates import CandidateIndex, generate_candidates
    from app.services.drug import get_drug_profile

    idx = CandidateIndex(drug_repo=drug_fixture_repo)
    idx.gene_target_available = False
    idx.gene_target_unavailable_reason = "HGNC file missing (test)"
    idx._build_pathway(drug_fixture_frames["drug_targets"], fake_pathway_index)

    res = generate_candidates(candidate_disease_profile, index=idx)
    cand = next(c for c in res.candidates if c.drug_id == "DRUG:001")  # via pathway only
    dp = get_drug_profile("DRUG:001", repository=drug_fixture_repo, enrich_pathways=False)

    v = build_feature_vector(cand, candidate_disease_profile, dp, index=idx)
    assert v.has_gene_target_bridge is False
    assert v.disease_gene_hgnc_mapped_count == 0
    assert v.drug_target_hgnc_mapped_count == 0
    assert v.matched_gene_target_count == 0
    assert v.fraction_of_drug_targets_matching_disease_genes is None
    assert v.fraction_of_disease_genes_targeted_by_drug is None
    assert "gene_target_bridge" in v.metadata.unavailable
    # pathway route still produced features
    assert v.matched_pathway_count == 1


def test_deterministic_output(feature_inputs):
    a = build_feature_vector(**_kw(feature_inputs))
    b = build_feature_vector(**_kw(feature_inputs))
    assert a.model_dump() == b.model_dump()


def test_no_nan_or_infinity(feature_inputs, empty_disease_profile, candidate_fixture_index,
                            drug_fixture_repo):
    from app.services.drug import get_drug_profile

    vectors = [build_feature_vector(**_kw(feature_inputs))]
    cand = CandidateDrug(drug_id="DRUG:001", drug_name="x", disease_id="DIS:E1",
                         disease_name="empty disease", methods=[], reasons=[])
    dp = get_drug_profile("DRUG:001", repository=drug_fixture_repo, enrich_pathways=False)
    vectors.append(build_feature_vector(cand, empty_disease_profile, dp,
                                        index=candidate_fixture_index))
    for v in vectors:
        for name, val in v.to_feature_dict().items():
            assert val is None or not (
                isinstance(val, float) and (math.isnan(val) or math.isinf(val))
            ), name


def test_no_score_or_ranking_fields_anywhere():
    forbidden = {"score", "probability", "confidence", "rank", "ranking", "prediction",
                 "weight", "similarity", "repurposing_score", "efficacy", "label"}
    for model in (FeatureVector, FeatureVectorMetadata):
        assert not (set(model.model_fields) & forbidden), model.__name__
    v_fields = set(FeatureVector.model_fields)
    # everything is a count / ratio(fraction) / bool / dict / identity / metadata
    assert {"disease_id", "drug_id"} <= v_fields
    assert any(f.startswith("fraction_") for f in v_fields)


def test_invalid_inputs_raise(feature_inputs):
    fi = feature_inputs
    with pytest.raises(InvalidFeatureInputError):
        build_feature_vector("not a candidate", fi["disease_profile"], fi["drug_profile"])
    with pytest.raises(InvalidFeatureInputError):
        build_feature_vector(fi["candidate"], fi["drug_profile"], fi["drug_profile"])
    # drug id mismatch between candidate and drug profile
    other = fi["candidate"].model_copy(update={"drug_id": "DRUG:999"})
    with pytest.raises(InvalidFeatureInputError):
        build_feature_vector(other, fi["disease_profile"], fi["drug_profile"],
                             index=fi["index"])


def test_no_fabricated_relationships(feature_inputs):
    """Matched counts never exceed what the real inputs allow."""
    v = build_feature_vector(**_kw(feature_inputs))
    assert v.matched_gene_target_count <= v.disease_gene_hgnc_mapped_count
    assert v.matched_gene_target_count <= v.drug_target_hgnc_mapped_count
    assert v.matched_pathway_count <= v.disease_pathway_count
    assert v.matched_pathway_count <= v.drug_pathway_count
    for frac in (
        v.fraction_of_drug_targets_matching_disease_genes,
        v.fraction_of_disease_genes_targeted_by_drug,
        v.fraction_of_drug_pathways_matching_disease_pathways,
        v.fraction_of_disease_pathways_matching_drug_pathways,
    ):
        assert frac is None or 0.0 <= frac <= 1.0


def test_batch_and_feature_rows(candidate_disease_profile, candidate_fixture_index):
    from app.services.candidates import generate_candidates

    res = generate_candidates(candidate_disease_profile, index=candidate_fixture_index)
    vectors = build_feature_vectors(
        candidate_disease_profile, res.candidates, index=candidate_fixture_index
    )
    assert len(vectors) == res.candidate_count == 1
    rows = feature_rows(vectors)
    assert rows[0]["disease_id"] == "DIS:C1" and rows[0]["drug_id"] == "DRUG:001"
    assert "score" not in rows[0] and "rank" not in rows[0]
    assert rows[0]["matched_gene_target_count"] == 1
    # dict features flattened
    assert rows[0]["action_type__INHIBITOR"] == 1


# --- real Level 1..4 data ---------------------------------------
def test_gbm_end_to_end_feature_pipeline(real_candidate_index):
    from app.services.candidates import generate_candidates
    from app.services.disease import build_disease_profile

    profile = build_disease_profile("Glioblastoma")
    res = generate_candidates(profile, index=real_candidate_index)
    vectors = build_feature_vectors(profile, res.candidates, index=real_candidate_index)

    assert len(vectors) == res.candidate_count > 0
    ids = {(v.disease_id, v.drug_id) for v in vectors}
    assert len(ids) == len(vectors)                      # one vector per candidate

    for v in vectors:
        assert v.disease_id == profile.disease_id
        assert v.disease_gene_count == len(profile.genes)
        assert v.disease_pathway_count == len(
            {p.reactome_id for p in profile.pathways if p.reactome_id}
        )
        # a candidate must have at least one real relationship feature > 0
        assert (v.matched_gene_target_count > 0) or (v.matched_pathway_count > 0)
        # no NaN / inf, all fractions in [0, 1] or None
        for name, val in v.to_feature_dict().items():
            if isinstance(val, float):
                assert not math.isnan(val) and not math.isinf(val), name
                if name.startswith("fraction_"):
                    assert 0.0 <= val <= 1.0

    # gene-target-only candidates: no pathway overlap; pathway-only: no gene match
    for v in vectors:
        if v.generated_by_gene_target and not v.generated_by_pathway:
            assert v.matched_pathway_count == 0
        if v.generated_by_pathway and not v.generated_by_gene_target:
            assert v.matched_gene_target_count == 0


def test_gbm_features_are_disease_specific(real_candidate_index):
    from app.services.candidates import generate_candidates
    from app.services.disease import build_disease_profile

    def vectors_for(name):
        p = build_disease_profile(name)
        r = generate_candidates(p, index=real_candidate_index)
        return {v.drug_id: v for v in build_feature_vectors(p, r.candidates, index=real_candidate_index)}

    gbm = vectors_for("glioblastoma")
    t2d = vectors_for("type 2 diabetes mellitus")
    shared = set(gbm) & set(t2d)
    assert shared  # some drugs are candidates for both
    # ... but their disease-side features differ
    assert any(
        gbm[d].matched_pathway_count != t2d[d].matched_pathway_count
        or gbm[d].matched_gene_target_count != t2d[d].matched_gene_target_count
        for d in shared
    )
    assert all(gbm[d].disease_id != t2d[d].disease_id for d in shared)


def _kw(fi: dict) -> dict:
    return {
        "candidate": fi["candidate"],
        "disease_profile": fi["disease_profile"],
        "drug_profile": fi["drug_profile"],
        "index": fi["index"],
    }
