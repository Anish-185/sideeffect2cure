"""Phase 10 — evidence graph tests.

All unit tests below use small synthetic fixtures (no real data / network
dependency). One real end-to-end test runs the actual GBM pipeline and is
skipped gracefully if Level 1 data has not been ingested locally.
"""

from __future__ import annotations

import pytest

from app.models.candidate import (
    CandidateDrug,
    CandidateGenerationReason,
    GenerationMethod,
    GeneTargetMatch,
    PathwayMatch,
)
from app.models.fusion import (
    DrugCharacterizationContext,
    EvidenceComponent,
    EvidenceFusionResult,
    FusionProvenance,
    SideEffectContext,
)
from app.models.graph import GraphEdgeType, GraphNodeType
from app.services.explanation.context import build_explanation_context
from app.services.explanation.deterministic import DeterministicExplanationProvider
from app.services.graph import (
    InconsistentGraphInputError,
    build_candidate_graph,
    build_evidence_graph,
)
from app.services.ranking import rank_candidates

_DID = "DIS:000035"


def _gt_reason(disease_gene_id: str, drug_target_id: str, hgnc_id: str = "HGNC:3236", symbol: str = "EGFR") -> CandidateGenerationReason:
    return CandidateGenerationReason(
        method=GenerationMethod.GENE_TARGET,
        gene_target=GeneTargetMatch(
            hgnc_id=hgnc_id,
            gene_symbol=symbol,
            disease_gene_id=disease_gene_id,
            disease_gene_ensembl_id="ENSG00000146648",
            disease_gene_source="opentargets",
            drug_target_id=drug_target_id,
            drug_target_name="Epidermal growth factor receptor",
            drug_target_uniprot_id="P00533",
            drug_action_type="INHIBITOR",
            drug_target_source="chembl",
        ),
    )


def _pw_reason(reactome_id: str = "R-HSA-1257604") -> CandidateGenerationReason:
    return CandidateGenerationReason(
        method=GenerationMethod.PATHWAY,
        pathway=PathwayMatch(
            reactome_id=reactome_id,
            pathway_name="Signalling by EGFR",
            disease_pathway_id="PATH:000042",
            disease_pathway_source="derived:opentargets+reactome",
            disease_gene_support_count=6,
            drug_pathway_source="derived:chembl-targets+reactome",
            drug_supporting_target_count=2,
        ),
    )


def _candidate_drug(
    drug_id: str,
    *,
    reasons: list[CandidateGenerationReason] | None = None,
) -> CandidateDrug:
    reasons = reasons if reasons is not None else [_gt_reason("GENE:000201", "TGT:000501"), _pw_reason()]
    methods = sorted({r.method for r in reasons}, key=lambda m: m.value)
    gene_ids, gene_symbols, disease_gene_ids, target_ids, pathway_ids = [], [], [], [], []
    for r in reasons:
        if r.gene_target:
            gene_ids.append(r.gene_target.hgnc_id)
            gene_symbols.append(r.gene_target.gene_symbol)
            disease_gene_ids.append(r.gene_target.disease_gene_id)
            target_ids.append(r.gene_target.drug_target_id)
        if r.pathway:
            pathway_ids.append(r.pathway.reactome_id)
    return CandidateDrug(
        drug_id=drug_id,
        drug_name=f"drug-{drug_id[-3:]}",
        disease_id=_DID,
        disease_name="glioblastoma",
        methods=methods,
        reasons=reasons,
        matched_gene_hgnc_ids=sorted(set(gene_ids)),
        matched_gene_symbols=sorted({s for s in gene_symbols if s}),
        matched_disease_gene_ids=sorted(set(disease_gene_ids)),
        matched_drug_target_ids=sorted(set(target_ids)),
        matched_pathway_reactome_ids=sorted(set(pathway_ids)),
    )


def _comp(name: str, value: float | None, weight: float, avail: bool = True) -> EvidenceComponent:
    return EvidenceComponent(
        name=name,
        available=avail,
        value=value,
        configured_weight=weight,
        effective_weight=weight if avail else None,
        contribution_points=(round((value or 0.0) * weight * 100, 4) if avail else None),
        calculation_method=f"{name} formula",
        provenance=f"{name} source",
        supporting={"model_output": 0.8, "baseline_output": 0.5, "top_feature_names": ["f1", "f2"]}
        if name == "ml"
        else {"k": 1},
        unavailable_reason=None if avail else "not assessable",
    )


def _fusion(
    drug_id: str,
    score: float = 84.9,
    *,
    gene_target_available: bool = True,
    pathway_available: bool = True,
    ml_available: bool = True,
) -> EvidenceFusionResult:
    comps = [
        _comp("gene_target", 0.87 if gene_target_available else None, 0.45, avail=gene_target_available),
        _comp("pathway", 0.74 if pathway_available else None, 0.25, avail=pathway_available),
        _comp("ml", 0.91 if ml_available else None, 0.30, avail=ml_available),
    ]
    return EvidenceFusionResult(
        disease_id=_DID,
        drug_id=drug_id,
        disease_name="glioblastoma",
        drug_name=f"drug-{drug_id[-3:]}",
        repurposing_score=score,
        components=comps,
        n_components_available=sum(c.available for c in comps),
        n_components_unavailable=sum(not c.available for c in comps),
        weights_configured={"gene_target": 0.45, "pathway": 0.25, "ml": 0.30},
        weights_renormalized_over_available=not all([gene_target_available, pathway_available, ml_available]),
        side_effect_context=SideEffectContext(side_effect_count=12, has_sider_evidence=True),
        drug_characterization=DrugCharacterizationContext(
            drug_target_count=4, drug_pathway_count=53, mechanism_count=4,
        ),
        matched_gene_hgnc_ids=["HGNC:3236"],
        matched_disease_gene_ids=["GENE:000201"],
        matched_drug_target_ids=["TGT:000501"],
        matched_pathway_reactome_ids=["R-HSA-1257604"],
        generation_methods=["gene_target", "pathway"],
        ml_model_name="random_forest" if ml_available else None,
        ml_model_output=0.91 if ml_available else None,
        ml_baseline_output=0.50 if ml_available else None,
        provenance=FusionProvenance(normalization="n", disclaimer="not clinical efficacy"),
    )


def _ranked(drug_id: str = "DRUG:000124", score: float = 84.9, **fusion_kwargs) -> tuple:
    """Returns (RankedCandidate, CandidateDrug) built from the same drug_id."""
    fusion = _fusion(drug_id, score, **fusion_kwargs)
    ranked = rank_candidates([fusion]).candidates[0]
    reasons = []
    if fusion_kwargs.get("gene_target_available", True) is not False:
        reasons.append(_gt_reason("GENE:000201", "TGT:000501"))
    if fusion_kwargs.get("pathway_available", True) is not False:
        reasons.append(_pw_reason())
    generation_candidate = _candidate_drug(drug_id, reasons=reasons)
    return ranked, generation_candidate


def _explanation_for(ranked):
    ctx = build_explanation_context(ranked)
    return DeterministicExplanationProvider().explain(ranked, ctx)


# --- basic graph creation -------------------------------------------------


def test_graph_creation_basic():
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    assert graph.disease_id == _DID
    assert graph.drug_id == ranked.drug_id
    assert graph.metadata.n_nodes == len(graph.nodes)
    assert graph.metadata.n_edges == len(graph.edges)
    assert graph.metadata.n_candidates == 1


def test_disease_node_correct():
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    node = graph.node(f"disease:{_DID}")
    assert node is not None
    assert node.type == GraphNodeType.DISEASE
    assert node.label == "glioblastoma"
    assert node.metadata["disease_id"] == _DID


def test_drug_node_correct():
    ranked, gen = _ranked("DRUG:000124")
    graph = build_candidate_graph(ranked, gen)
    node = graph.node("drug:DRUG:000124")
    assert node is not None
    assert node.type == GraphNodeType.DRUG
    assert node.label == "drug-124"
    assert node.metadata["drug_id"] == "DRUG:000124"


def test_disease_gene_node():
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    node = graph.node("disease_gene:GENE:000201")
    assert node is not None
    assert node.type == GraphNodeType.DISEASE_GENE
    assert node.label == "EGFR"
    assert node.metadata["hgnc_id"] == "HGNC:3236"
    assert node.metadata["source"] == "opentargets"


def test_drug_target_node():
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    node = graph.node("drug_target:TGT:000501")
    assert node is not None
    assert node.type == GraphNodeType.DRUG_TARGET
    assert node.label == "Epidermal growth factor receptor"
    assert node.metadata["uniprot_id"] == "P00533"
    assert node.metadata["action_type"] == "INHIBITOR"
    assert node.metadata["source"] == "chembl"


def test_pathway_node():
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    node = graph.node("pathway:R-HSA-1257604")
    assert node is not None
    assert node.type == GraphNodeType.PATHWAY
    assert node.label == "Signalling by EGFR"
    assert node.metadata["disease_gene_support_count"] == 6
    assert node.metadata["drug_supporting_target_count"] == 2


def test_prediction_representation():
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    node = graph.node(f"prediction:{ranked.drug_id}")
    assert node is not None
    assert node.type == GraphNodeType.PREDICTION
    assert node.metadata["model_name"] == "random_forest"
    assert node.metadata["model_output"] == 0.91
    assert node.metadata["baseline_output"] == 0.50
    assert node.metadata["top_feature_names"] == ["f1", "f2"]


def test_evidence_component_representation():
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    for name in ("gene_target", "pathway", "ml"):
        node = graph.node(f"evidence:{ranked.drug_id}:{name}")
        assert node is not None, name
        assert node.type == GraphNodeType.EVIDENCE_COMPONENT
        assert node.metadata["name"] == name
        assert node.metadata["contribution_points"] is not None


def test_score_representation():
    ranked, gen = _ranked(score=84.9)
    graph = build_candidate_graph(ranked, gen)
    node = graph.node(f"score:{ranked.drug_id}")
    assert node is not None
    assert node.type == GraphNodeType.SCORE
    assert node.metadata["repurposing_score"] == 84.9
    assert "84.9" in node.label


def test_rank_representation():
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    node = graph.node(f"rank:{ranked.drug_id}")
    assert node is not None
    assert node.type == GraphNodeType.RANK
    assert node.metadata["rank"] == ranked.rank == 1
    assert node.label == "Rank #1"


def test_ai_explanation_representation():
    ranked, gen = _ranked()
    explanation = _explanation_for(ranked)
    graph = build_candidate_graph(ranked, gen, explanation=explanation)
    node = graph.node(f"explanation:{ranked.drug_id}")
    assert node is not None
    assert node.type == GraphNodeType.EXPLANATION
    assert node.metadata["summary"] == explanation.summary
    assert node.metadata["provider"] == explanation.provenance.provider


def test_no_explanation_node_when_not_supplied():
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    assert graph.node(f"explanation:{ranked.drug_id}") is None
    assert graph.metadata.includes_explanation is False


# --- edges + provenance ----------------------------------------------------


def test_correct_biological_edges():
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    edge_pairs = {(e.source, e.target, e.type) for e in graph.edges}
    disease_id, gene_id, target_id, pathway_id, drug_id = (
        f"disease:{_DID}", "disease_gene:GENE:000201", "drug_target:TGT:000501",
        "pathway:R-HSA-1257604", f"drug:{ranked.drug_id}",
    )
    assert (disease_id, gene_id, GraphEdgeType.ASSOCIATED_WITH) in edge_pairs
    assert (gene_id, target_id, GraphEdgeType.MATCHED_TO) in edge_pairs
    assert (drug_id, target_id, GraphEdgeType.HAS_TARGET) in edge_pairs
    assert (disease_id, pathway_id, GraphEdgeType.ASSOCIATED_WITH) in edge_pairs
    assert (drug_id, pathway_id, GraphEdgeType.PARTICIPATES_IN) in edge_pairs


def test_no_target_belongs_to_pathway_edge():
    """Level 4 evidence only carries an aggregate pathway support count, not a
    specific target<->pathway membership — so that edge is never fabricated."""
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    assert all(e.type != "belongs_to" for e in graph.edges)


def test_provenance_preservation_gene_target():
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    gene_edge = next(
        e for e in graph.edges
        if e.source == f"disease:{_DID}" and e.target == "disease_gene:GENE:000201"
    )
    assert gene_edge.provenance == "opentargets"
    target_edge = next(
        e for e in graph.edges
        if e.source == f"drug:{ranked.drug_id}" and e.target == "drug_target:TGT:000501"
    )
    assert target_edge.provenance == "chembl"


def test_provenance_preservation_pathway():
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    disease_pathway_edge = next(
        e for e in graph.edges
        if e.source == f"disease:{_DID}" and e.target == "pathway:R-HSA-1257604"
    )
    assert disease_pathway_edge.provenance == "derived:opentargets+reactome"
    drug_pathway_edge = next(
        e for e in graph.edges
        if e.source == f"drug:{ranked.drug_id}" and e.target == "pathway:R-HSA-1257604"
    )
    assert drug_pathway_edge.provenance == "derived:chembl-targets+reactome"


def test_evidence_edges_carry_component_provenance():
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    ml_edge = next(
        e for e in graph.edges
        if e.target == f"evidence:{ranked.drug_id}:ml"
    )
    assert ml_edge.provenance == "ml source"  # from EvidenceComponent.provenance in the fixture


# --- deduplication + determinism -------------------------------------------


def test_node_deduplication_across_candidates():
    """Two different drugs sharing the same disease gene must collapse to one
    disease_gene node (and one disease->gene edge), not two."""
    fusion_a = _fusion("DRUG:AAA", 80.0)
    fusion_b = _fusion("DRUG:BBB", 70.0)
    ranked_result = rank_candidates([fusion_a, fusion_b])

    gen_a = _candidate_drug("DRUG:AAA", reasons=[_gt_reason("GENE:000201", "TGT:AAA1")])
    gen_b = _candidate_drug("DRUG:BBB", reasons=[_gt_reason("GENE:000201", "TGT:BBB1")])

    graph = build_evidence_graph(ranked_result.candidates, [gen_a, gen_b])

    gene_nodes = [n for n in graph.nodes if n.id == "disease_gene:GENE:000201"]
    assert len(gene_nodes) == 1
    gene_edges = [
        e for e in graph.edges
        if e.source == f"disease:{_DID}" and e.target == "disease_gene:GENE:000201"
    ]
    assert len(gene_edges) == 1
    # but each drug still has its OWN target node + has_target edge
    assert graph.node("drug_target:TGT:AAA1") is not None
    assert graph.node("drug_target:TGT:BBB1") is not None


def test_edge_and_node_determinism():
    ranked, gen = _ranked()
    explanation = _explanation_for(ranked)
    g1 = build_candidate_graph(ranked, gen, explanation=explanation)
    g2 = build_candidate_graph(ranked, gen, explanation=explanation)
    assert [n.model_dump() for n in g1.nodes] == [n.model_dump() for n in g2.nodes]
    assert [e.model_dump() for e in g1.edges] == [e.model_dump() for e in g2.edges]


# --- missing evidence handling ----------------------------------------------


def test_empty_evidence_handling():
    """A candidate with no biological reasons at all must not crash the
    builder and must produce no biological nodes."""
    fusion = _fusion("DRUG:EMPTY", 10.0, gene_target_available=False, pathway_available=False)
    ranked = rank_candidates([fusion]).candidates[0]
    gen = _candidate_drug("DRUG:EMPTY", reasons=[])

    graph = build_candidate_graph(ranked, gen)

    assert not any(n.type == GraphNodeType.DISEASE_GENE for n in graph.nodes)
    assert not any(n.type == GraphNodeType.DRUG_TARGET for n in graph.nodes)
    assert not any(n.type == GraphNodeType.PATHWAY for n in graph.nodes)
    # core nodes still present
    assert graph.node(f"drug:{ranked.drug_id}") is not None
    assert graph.node(f"score:{ranked.drug_id}") is not None
    assert graph.node(f"rank:{ranked.drug_id}") is not None


def test_missing_pathway_evidence_no_crash_no_fake_node():
    ranked, gen = _ranked(pathway_available=False)
    graph = build_candidate_graph(ranked, gen)
    assert graph.node(f"evidence:{ranked.drug_id}:pathway") is None
    # gene-target evidence (independent) is unaffected
    assert graph.node(f"evidence:{ranked.drug_id}:gene_target") is not None


def test_missing_ml_evidence_no_crash_no_fake_node():
    ranked, gen = _ranked(ml_available=False)
    graph = build_candidate_graph(ranked, gen)
    assert graph.node(f"evidence:{ranked.drug_id}:ml") is None
    assert graph.node(f"prediction:{ranked.drug_id}") is None
    assert graph.metadata.includes_ml_evidence is False
    # other evidence unaffected
    assert graph.node(f"evidence:{ranked.drug_id}:gene_target") is not None


# --- one-candidate / top-N ---------------------------------------------------


def test_one_candidate_graph():
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    assert graph.drug_id == ranked.drug_id
    assert graph.drug_ids == [ranked.drug_id]
    assert graph.metadata.n_candidates == 1


def test_top_n_graph():
    fusions = [_fusion(f"DRUG:{i:03d}", float(90 - i)) for i in range(5)]
    ranked_result = rank_candidates(fusions)
    gens = [_candidate_drug(c.drug_id) for c in ranked_result.candidates]

    graph = build_evidence_graph(ranked_result.candidates, gens)

    assert graph.drug_id is None  # ambiguous with >1 candidate
    assert graph.drug_ids == [c.drug_id for c in ranked_result.candidates]
    assert graph.metadata.n_candidates == 5
    assert all(graph.node(f"drug:{did}") is not None for did in graph.drug_ids)


# --- no fabrication -----------------------------------------------------------


def test_no_dangling_edges():
    ranked, gen = _ranked()
    explanation = _explanation_for(ranked)
    graph = build_candidate_graph(ranked, gen, explanation=explanation)
    node_ids = {n.id for n in graph.nodes}
    for e in graph.edges:
        assert e.source in node_ids, f"dangling edge source {e.source!r}"
        assert e.target in node_ids, f"dangling edge target {e.target!r}"


def test_no_new_biological_inference_only_known_edge_types():
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    known = {t.value for t in GraphEdgeType}
    assert all(e.type.value in known for e in graph.edges)


def test_gene_node_metadata_matches_source_exactly():
    """The graph must not add/derive a field beyond what the CandidateDrug's
    own GeneTargetMatch carried."""
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    m = gen.reasons[0].gene_target
    node = graph.node(f"disease_gene:{m.disease_gene_id}")
    assert node.metadata["hgnc_id"] == m.hgnc_id
    assert node.metadata["gene_symbol"] == m.gene_symbol
    assert node.metadata["ensembl_id"] == m.disease_gene_ensembl_id
    assert node.metadata["source"] == m.disease_gene_source


def test_score_and_rank_not_recalculated():
    ranked, gen = _ranked(score=73.25)
    graph = build_candidate_graph(ranked, gen)
    assert graph.node(f"score:{ranked.drug_id}").metadata["repurposing_score"] == 73.25 == ranked.repurposing_score
    assert graph.node(f"rank:{ranked.drug_id}").metadata["rank"] == ranked.rank


# --- input validation ---------------------------------------------------------


def test_empty_candidate_list_raises():
    with pytest.raises(InconsistentGraphInputError):
        build_evidence_graph([], [])


def test_mismatched_disease_drug_raises():
    ranked, _gen = _ranked("DRUG:AAA")
    wrong_gen = _candidate_drug("DRUG:BBB")  # different drug_id than ranked candidate
    with pytest.raises(InconsistentGraphInputError):
        build_evidence_graph([ranked], [wrong_gen])


def test_multiple_diseases_raises():
    fusion_a = _fusion("DRUG:AAA", 80.0)
    ranked_a = rank_candidates([fusion_a]).candidates[0]
    fusion_b = EvidenceFusionResult(
        disease_id="DIS:999999", drug_id="DRUG:BBB", disease_name="other disease",
        drug_name="drug-bbb", repurposing_score=50.0,
        components=[_comp("gene_target", 0.5, 0.45), _comp("pathway", 0.5, 0.25), _comp("ml", 0.5, 0.30)],
        n_components_available=3, n_components_unavailable=0,
        weights_configured={"gene_target": 0.45, "pathway": 0.25, "ml": 0.30},
        weights_renormalized_over_available=False,
        side_effect_context=SideEffectContext(side_effect_count=1, has_sider_evidence=False),
        drug_characterization=DrugCharacterizationContext(drug_target_count=1, drug_pathway_count=1, mechanism_count=1),
        provenance=FusionProvenance(normalization="n", disclaimer="not clinical efficacy"),
    )
    ranked_b = rank_candidates([fusion_b]).candidates[0]
    gen_a = _candidate_drug("DRUG:AAA")
    with pytest.raises(InconsistentGraphInputError):
        build_evidence_graph([ranked_a, ranked_b], [gen_a])


# --- frontend-friendly output --------------------------------------------------


def test_to_frontend_dict_shape():
    ranked, gen = _ranked()
    graph = build_candidate_graph(ranked, gen)
    d = graph.to_frontend_dict()
    assert set(d.keys()) == {"nodes", "edges"}
    assert isinstance(d["nodes"], list) and isinstance(d["edges"], list)
    assert all("id" in n and "type" in n and "label" in n for n in d["nodes"])
    assert all("id" in e and "source" in e and "target" in e and "type" in e for e in d["edges"])


# --- real end-to-end (GBM) -----------------------------------------------------


def test_real_gbm_top_candidate_graph():
    from app.services.disease.errors import DiseaseIntelligenceError
    from app.services.graph import build_graph_for_disease

    try:
        graph = build_graph_for_disease("Glioblastoma", top_n=1, include_explanations=False)
    except DiseaseIntelligenceError:
        pytest.skip("Level 1 processed data not present; run scripts/ingest_data.py")

    assert graph.disease_id and graph.drug_id
    assert graph.metadata.n_nodes > 0
    assert graph.metadata.n_edges > 0
    assert graph.node(f"disease:{graph.disease_id}") is not None
    assert graph.node(f"drug:{graph.drug_id}") is not None
    assert graph.node(f"score:{graph.drug_id}") is not None
    assert graph.node(f"rank:{graph.drug_id}") is not None
    node_ids = {n.id for n in graph.nodes}
    assert all(e.source in node_ids and e.target in node_ids for e in graph.edges)


def test_real_gbm_top3_graph_deterministic():
    from app.services.disease.errors import DiseaseIntelligenceError
    from app.services.graph import build_graph_for_disease

    try:
        g1 = build_graph_for_disease("Glioblastoma", top_n=3, include_explanations=False)
        g2 = build_graph_for_disease("Glioblastoma", top_n=3, include_explanations=False)
    except DiseaseIntelligenceError:
        pytest.skip("Level 1 processed data not present; run scripts/ingest_data.py")

    assert g1.metadata.n_candidates == len(g1.drug_ids) == 3
    assert [n.id for n in g1.nodes] == [n.id for n in g2.nodes]
    assert [e.id for e in g1.edges] == [e.id for e in g2.edges]
