"""Phase 8 — candidate ranking tests."""

from __future__ import annotations

import pytest

from app.models.fusion import (
    DrugCharacterizationContext,
    EvidenceComponent,
    EvidenceFusionResult,
    FusionProvenance,
    SideEffectContext,
)
from app.models.ranking import RankedCandidate, RankedCandidateResult, RankingProvenance
from app.services.ranking import (
    DuplicateCandidateError,
    InvalidTopNError,
    rank_candidates,
)

_DID = "DIS:000035"


def _comp(name: str, value: float | None, weight: float, avail: bool = True) -> EvidenceComponent:
    return EvidenceComponent(
        name=name, available=avail, value=value, configured_weight=weight,
        effective_weight=weight if avail else None,
        contribution_points=(round((value or 0.0) * weight * 100, 4) if avail else None),
        calculation_method=f"{name} formula", provenance=f"{name} source",
        supporting={"k": 1},
        unavailable_reason=None if avail else "not assessable",
    )


def _fr(drug_id: str, score: float, *, disease_id: str = _DID, ml: bool = True,
        genes=None, targets=None, pathways=None) -> EvidenceFusionResult:
    comps = [_comp("gene_target", 0.6, 0.45), _comp("pathway", 0.5, 0.25)]
    comps.append(_comp("ml", 0.8, 0.30) if ml else _comp("ml", None, 0.30, avail=False))
    return EvidenceFusionResult(
        disease_id=disease_id, drug_id=drug_id,
        disease_name="glioblastoma", drug_name=f"drug-{drug_id[-3:]}",
        repurposing_score=score,
        components=comps,
        n_components_available=sum(c.available for c in comps),
        n_components_unavailable=sum(not c.available for c in comps),
        weights_configured={"gene_target": 0.45, "pathway": 0.25, "ml": 0.30},
        weights_renormalized_over_available=not ml,
        side_effect_context=SideEffectContext(side_effect_count=42, has_sider_evidence=True),
        drug_characterization=DrugCharacterizationContext(
            drug_target_count=3, drug_pathway_count=10, mechanism_count=3,
        ),
        matched_gene_hgnc_ids=genes or ["HGNC:1"],
        matched_disease_gene_ids=["GENE:1"],
        matched_drug_target_ids=targets or ["TGT:1"],
        matched_pathway_reactome_ids=pathways or ["R-HSA-1"],
        generation_methods=["gene_target", "pathway"],
        ml_model_name="random_forest" if ml else None,
        ml_model_output=0.8 if ml else None,
        ml_baseline_output=0.5 if ml else None,
        provenance=FusionProvenance(normalization="n", disclaimer="not clinical efficacy"),
    )


# --- ordering ---------------------------------------------------
def test_highest_score_gets_rank_1():
    out = rank_candidates([_fr("DRUG:A", 40.0), _fr("DRUG:B", 91.2), _fr("DRUG:C", 73.5)])
    assert [(c.rank, c.drug_id, c.repurposing_score) for c in out.candidates] == [
        (1, "DRUG:B", 91.2), (2, "DRUG:C", 73.5), (3, "DRUG:A", 40.0),
    ]


def test_multiple_candidates_fully_ordered():
    scores = [10.0, 55.5, 99.9, 0.1, 55.4, 80.0]
    out = rank_candidates([_fr(f"DRUG:{i}", s) for i, s in enumerate(scores)])
    got = [c.repurposing_score for c in out.candidates]
    assert got == sorted(scores, reverse=True)
    assert [c.rank for c in out.candidates] == [1, 2, 3, 4, 5, 6]


def test_equal_scores_use_deterministic_drug_id_tie_break():
    a = rank_candidates([_fr("DRUG:C", 50.0), _fr("DRUG:A", 50.0), _fr("DRUG:B", 50.0)])
    b = rank_candidates([_fr("DRUG:B", 50.0), _fr("DRUG:C", 50.0), _fr("DRUG:A", 50.0)])
    assert [c.drug_id for c in a.candidates] == ["DRUG:A", "DRUG:B", "DRUG:C"]
    assert [c.drug_id for c in a.candidates] == [c.drug_id for c in b.candidates]  # order-independent
    assert [c.rank for c in a.candidates] == [1, 2, 3]  # ranks stay unique


# --- top_n -----------------------------------------------------
def test_default_returns_full_list():
    out = rank_candidates([_fr(f"DRUG:{i}", float(i)) for i in range(20)])
    assert out.n_candidates == 20
    assert out.provenance.top_n_applied is None


def test_top_n_selects_and_does_not_alter_scores():
    full = rank_candidates([_fr(f"DRUG:{i}", float(i * 3)) for i in range(15)])
    top5 = rank_candidates([_fr(f"DRUG:{i}", float(i * 3)) for i in range(15)], top_n=5)
    assert top5.n_candidates == 5
    assert [c.drug_id for c in top5.candidates] == [c.drug_id for c in full.candidates[:5]]
    assert [c.repurposing_score for c in top5.candidates] == [
        c.repurposing_score for c in full.candidates[:5]
    ]
    assert [c.rank for c in top5.candidates] == [1, 2, 3, 4, 5]
    assert top5.provenance.top_n_applied == 5 and top5.provenance.top_n_requested == 5


def test_top_n_one():
    out = rank_candidates([_fr("DRUG:A", 10.0), _fr("DRUG:B", 90.0)], top_n=1)
    assert out.n_candidates == 1 and out.candidates[0].drug_id == "DRUG:B"


def test_top_n_larger_than_count_returns_all():
    out = rank_candidates([_fr("DRUG:A", 10.0), _fr("DRUG:B", 20.0)], top_n=100)
    assert out.n_candidates == 2
    assert out.provenance.top_n_requested == 100 and out.provenance.top_n_applied == 2


def test_invalid_top_n_raises():
    fr = [_fr("DRUG:A", 1.0)]
    for bad in (0, -5, 2.5, "3", True):
        with pytest.raises((InvalidTopNError, TypeError, ValueError)):
            rank_candidates(fr, top_n=bad)  # type: ignore[arg-type]


# --- input edge cases ---------------------------------------
def test_empty_input():
    out = rank_candidates([])
    assert isinstance(out, RankedCandidateResult)
    assert out.candidates == [] and out.n_candidates == 0
    assert out.disease_id is None
    assert out.provenance.n_input == 0


def test_single_candidate():
    out = rank_candidates([_fr("DRUG:X", 55.0)])
    assert out.n_candidates == 1
    assert out.candidates[0].rank == 1 and out.candidates[0].drug_id == "DRUG:X"


def test_duplicate_drug_id_is_rejected_not_double_ranked():
    with pytest.raises(DuplicateCandidateError) as exc:
        rank_candidates([_fr("DRUG:A", 10.0), _fr("DRUG:B", 20.0), _fr("DRUG:A", 30.0)])
    assert exc.value.duplicates == ["DRUG:A"]


def test_wrong_input_type_raises():
    with pytest.raises(TypeError):
        rank_candidates("not a list")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        rank_candidates([{"drug_id": "x"}])  # type: ignore[list-item]


# --- evidence / provenance preservation --------------------
def test_evidence_components_preserved():
    src = _fr("DRUG:A", 70.0)
    out = rank_candidates([src, _fr("DRUG:B", 10.0)])
    c = out.candidates[0]
    assert c.drug_id == "DRUG:A"
    assert c.fusion == src                               # whole Phase 7 record embedded
    assert {x.name for x in c.fusion.components} == {"gene_target", "pathway", "ml"}
    gt = c.component("gene_target")
    assert gt.value == 0.6 and gt.configured_weight == 0.45
    assert gt.effective_weight == 0.45 and gt.contribution_points is not None
    assert gt.calculation_method and gt.provenance and gt.supporting == {"k": 1}


def test_provenance_and_ids_preserved():
    src = _fr("DRUG:A", 70.0, genes=["HGNC:9", "HGNC:8"], targets=["TGT:9"],
              pathways=["R-HSA-9", "R-HSA-8"])
    out = rank_candidates([src])
    c = out.candidates[0]
    assert c.disease_id == _DID and c.drug_id == "DRUG:A"
    assert c.matched_gene_hgnc_ids == ["HGNC:9", "HGNC:8"]
    assert c.matched_disease_gene_ids == ["GENE:1"]
    assert c.matched_drug_target_ids == ["TGT:9"]
    assert c.matched_pathway_reactome_ids == ["R-HSA-9", "R-HSA-8"]
    assert c.generation_methods == ["gene_target", "pathway"]
    assert c.fusion.provenance.scoring_version == "1.0"
    assert out.provenance.scoring_version == "1.0"
    assert out.disease_id == _DID


def test_ml_unavailable_candidate_still_ranks_with_its_breakdown():
    out = rank_candidates([_fr("DRUG:A", 60.0, ml=False), _fr("DRUG:B", 90.0)])
    a = next(c for c in out.candidates if c.drug_id == "DRUG:A")
    assert a.component("ml").available is False
    assert a.component("gene_target").available is True
    assert a.repurposing_score == 60.0


# --- determinism / no recalculation -----------------------
def test_deterministic():
    inp = [_fr(f"DRUG:{i}", float((i * 37) % 100)) for i in range(30)]
    a = rank_candidates(inp)
    b = rank_candidates([_fr(f"DRUG:{i}", float((i * 37) % 100)) for i in range(30)])
    assert a.model_dump() == b.model_dump()


def test_no_score_recalculation():
    inp = [_fr("DRUG:A", 12.3456), _fr("DRUG:B", 88.7654)]
    out = rank_candidates(inp)
    by_id = {c.drug_id: c for c in out.candidates}
    assert by_id["DRUG:A"].repurposing_score == 12.3456
    assert by_id["DRUG:B"].repurposing_score == 88.7654
    assert by_id["DRUG:A"].fusion.repurposing_score == 12.3456
    assert out.provenance.scores_recalculated is False
    assert out.provenance.biology_recalculated is False


def test_no_new_biology_no_clinical_no_ranking_score_fields():
    forbidden = {"efficacy", "clinical_efficacy", "treatment_probability", "cure",
                 "recommendation", "safety_score", "similarity", "new_score",
                 "priority_score", "response_probability", "success_probability"}
    for model in (RankedCandidate, RankedCandidateResult, RankingProvenance):
        assert not (set(model.model_fields) & forbidden), model.__name__
    out = rank_candidates([_fr("DRUG:A", 50.0)])
    text = (out.provenance.interpretation + " " + out.provenance.disclaimer).lower()
    assert "not" in text and (
        "clinical efficacy" in text or "efficacy" in text or "cure" in text
    )
    assert "not a medical recommendation" in out.provenance.interpretation.lower()


def test_table_rows_projection_keeps_breakdown():
    out = rank_candidates([_fr("DRUG:A", 70.0), _fr("DRUG:B", 40.0)])
    rows = out.table_rows()
    assert [r["rank"] for r in rows] == [1, 2]
    assert rows[0]["repurposing_score"] == 70.0
    assert rows[0]["gene_target_value"] == 0.6 and rows[0]["gene_target_points"] is not None
    assert "ml_value" in rows[0]
    # the full model still has everything
    assert out.candidates[0].fusion.components


# --- real GBM end-to-end --------------------------------
def test_gbm_end_to_end_ranking(real_candidate_index):
    from app.services.candidates import generate_candidates
    from app.services.disease import build_disease_profile
    from app.services.features import build_feature_vectors
    from app.services.fusion import fuse_all
    from app.services.ml import predict
    from app.services.ml.model import ModelNotTrainedError

    profile = build_disease_profile("Glioblastoma")
    res = generate_candidates(profile, index=real_candidate_index)
    vectors = build_feature_vectors(profile, res.candidates, index=real_candidate_index)
    try:
        preds = predict(vectors, candidates=res.candidates)
    except ModelNotTrainedError:
        preds = None
    fused = fuse_all(res.candidates, vectors, preds)

    ranked = rank_candidates(fused)
    assert ranked.n_candidates == len(fused) == res.candidate_count
    assert ranked.disease_id == profile.disease_id

    scores = [c.repurposing_score for c in ranked.candidates]
    assert scores == sorted(scores, reverse=True)                 # descending
    assert [c.rank for c in ranked.candidates] == list(range(1, len(scores) + 1))
    # tie-break check: equal-score neighbours are drug_id-ordered
    for i in range(len(ranked.candidates) - 1):
        a, b = ranked.candidates[i], ranked.candidates[i + 1]
        if a.repurposing_score == b.repurposing_score:
            assert a.drug_id < b.drug_id

    # scores identical to Phase 7 (nothing recalculated)
    fused_by_id = {f.drug_id: f.repurposing_score for f in fused}
    assert all(c.repurposing_score == fused_by_id[c.drug_id] for c in ranked.candidates)

    # every ranked candidate keeps the full evidence breakdown + graph ids
    for c in ranked.candidates:
        assert c.disease_id == profile.disease_id and c.drug_id.startswith("DRUG:")
        assert c.fusion.components and c.fusion.provenance
        pts = sum(x.contribution_points for x in c.fusion.components
                  if x.contribution_points is not None)
        assert c.repurposing_score == pytest.approx(pts, abs=1e-2)

    # top_n slice: same first-k, scores untouched
    top10 = rank_candidates(fused, top_n=10)
    assert top10.n_candidates == min(10, len(fused))
    assert [c.drug_id for c in top10.candidates] == [c.drug_id for c in ranked.candidates[:10]]
    assert [c.repurposing_score for c in top10.candidates] == scores[:10]

    # determinism on real data
    assert [c.drug_id for c in rank_candidates(fused).candidates] == [
        c.drug_id for c in ranked.candidates
    ]


def test_rank_for_disease_convenience(real_candidate_index):
    from app.services.ranking import rank_for_disease

    a = rank_for_disease("glioblastoma", top_n=10)
    b = rank_for_disease("MONDO_0018177", top_n=10)
    assert a.n_candidates == b.n_candidates == 10
    assert [c.drug_id for c in a.candidates] == [c.drug_id for c in b.candidates]
    assert [c.repurposing_score for c in a.candidates] == [c.repurposing_score for c in b.candidates]
    assert all(a.candidates[i].repurposing_score >= a.candidates[i + 1].repurposing_score
               for i in range(9))
