# Phase 10 — Evidence Graph

Phase 10 owns exactly this slice of the pipeline:

```
RankedCandidate + CandidateDrug (+ optional CandidateExplanation)
        ->  build_candidate_graph(...) / build_evidence_graph(...)
        ->  EvidenceGraph  (nodes[] + edges[], frontend-ready)
```

It is a **pure representation / visualization layer**. It discovers no new
relationship, computes no similarity or embedding, calls no external API, and
recalculates no score or rank — every node and edge is built from a field
that already exists on a real Level 2-9 pipeline object.

---

## Purpose

Make the reasoning behind a prioritized candidate visually understandable by
answering, structurally: *"why was this drug prioritized for this disease?"*

```
Disease -> Disease Genes -> Drug Targets -> Pathways -> Drug
        -> ML Prediction -> Evidence Fusion -> Repurposing Score -> Rank
        -> AI Explanation
```

---

## Graph data model (`app.models.graph`)

```python
class GraphNode(BaseModel):
    id: str
    type: GraphNodeType
    label: str
    metadata: dict

class GraphEdge(BaseModel):
    id: str
    source: str        # a GraphNode.id
    target: str        # a GraphNode.id
    type: GraphEdgeType
    metadata: dict
    provenance: str | None   # which pipeline level/source produced this relationship

class EvidenceGraph(BaseModel):
    disease_id: str
    disease_name: str
    drug_id: str | None       # set iff exactly one candidate is covered
    drug_ids: list[str]       # every candidate covered
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    metadata: EvidenceGraphMetadata   # counts, disclaimer, interpretation
```

`EvidenceGraph.to_frontend_dict()` returns `{"nodes": [...], "edges": [...]}`
— the shape most graph-visualization libraries (react-flow, cytoscape,
vis-network, d3) accept directly. No graph database, no Neo4j, no vector
database: this is a plain, local, in-memory Pydantic structure.

---

## Node types

| Type | Built from | Created when |
|---|---|---|
| `disease` | `RankedCandidate.disease_id/disease_name` | always (one per graph) |
| `drug` | `RankedCandidate.drug_id/drug_name` | always (one per candidate) |
| `disease_gene` | `CandidateDrug` reason's `GeneTargetMatch` | a real gene-target match exists |
| `drug_target` | same `GeneTargetMatch` | same |
| `pathway` | `CandidateDrug` reason's `PathwayMatch` | a real pathway match exists |
| `prediction` | `EvidenceFusionResult.ml_model_name/ml_model_output/ml_baseline_output` + the `ml` component's `supporting` | the ML evidence component is `available` |
| `evidence_component` | one per Phase 7 `EvidenceComponent` (`gene_target`/`pathway`/`ml`) | that component is `available` (§ "only when evidence actually exists" — see Missing evidence below) |
| `score` | `RankedCandidate.repurposing_score` | always |
| `rank` | `RankedCandidate.rank` | always |
| `explanation` | Phase 9 `CandidateExplanation` | one was supplied to the builder |

Nodes are never created "because the type exists" — each row above is
conditional on the corresponding evidence actually being present.

## Edge types

| Edge | Meaning | Provenance source |
|---|---|---|
| `disease -associated_with-> disease_gene` | disease-gene association | `GeneTargetMatch.disease_gene_source` (e.g. `opentargets`) |
| `disease_gene -matched_to-> drug_target` | same gene, via HGNC id join | fixed string naming the Level 4 HGNC-bridge method |
| `drug -has_target-> drug_target` | drug acts on this target | `GeneTargetMatch.drug_target_source` (e.g. `chembl`) |
| `disease -associated_with-> pathway` | pathway over-represented among disease genes | `PathwayMatch.disease_pathway_source` |
| `drug -participates_in-> pathway` | pathway reached via drug's targets | `PathwayMatch.drug_pathway_source` |
| `drug -received-> evidence_component` | drug received this Phase 7 evidence family | `EvidenceComponent.provenance` |
| `drug -received-> prediction` | drug received this Phase 6 model output | fixed string naming Level 6 |
| `drug -received-> score` | drug received this Phase 7 score | fixed string naming Phase 7 |
| `drug -ranked-> rank` | drug was placed at this rank | fixed string naming Phase 8 |
| `drug -explained_by-> explanation` | drug was narrated by Phase 9 | fixed string naming Phase 9 |

Only the edge types above exist; `GraphEdgeType` has no other member, so a
test can (and does) assert every edge in a graph is one of these.

---

## Provenance

Every biological edge carries `provenance` — the exact source string already
recorded by Level 4 (`GeneTargetMatch.disease_gene_source` /
`.drug_target_source`, `PathwayMatch.disease_pathway_source` /
`.drug_pathway_source`), not a new label invented here. Node `metadata` keeps
the underlying internal **and** external identifiers (`disease_gene_id`,
`hgnc_id`, `ensembl_id`; `drug_target_id`, `uniprot_id`; `reactome_id`) plus
support counts (`disease_gene_support_count`, `drug_supporting_target_count`)
— everything a future dashboard needs to show "where did this relationship
come from" on click, without re-querying anything.

---

## No new biological inference

The builder (`app.services.graph.build`) reads fields; it never computes one.
Concretely:

* Gene-target and pathway nodes/edges come **only** from
  `CandidateDrug.reasons` (`GeneTargetMatch` / `PathwayMatch`) — the exact
  Level 4 output, already produced by a deterministic HGNC-id join / Reactome
  intersection. No similarity, no embedding, no new gene/target/pathway
  lookup.
* Score, rank, and every evidence-component value/weight/contribution come
  **only** from the already-computed `EvidenceFusionResult` /
  `RankedCandidate` — never recalculated (`docs/evidence-fusion.md` /
  `docs/candidate-ranking.md` remain the source of truth).
  `test_score_and_rank_not_recalculated` and `test_edge_and_node_determinism`
  in `tests/test_evidence_graph.py` pin this down.
* The AI explanation node only narrates a `CandidateExplanation` Phase 9
  already produced — the graph never generates or edits explanation text.
* No network call, no new dataset, no literature/RAG/embedding lookup is made
  anywhere in this package.

### A deliberate scoping decision: no `Target -belongs_to-> Pathway` edge

The prompt's own illustrative diagram suggests a target→pathway edge.
Level 4's `PathwayMatch` only carries an **aggregate**
`drug_supporting_target_count` (how many of the drug's targets map into the
pathway) — it does not name *which* target. Asserting a specific
`drug_target -belongs_to-> pathway` edge would mean inventing a link the
supplied evidence does not actually contain, which §6 forbids. So Phase 10
represents the pathway relationship at the level the evidence actually
supports: `disease -associated_with-> pathway` and
`drug -participates_in-> pathway`, both carrying their real support counts,
and stops there. `test_no_target_belongs_to_pathway_edge` pins this down.

---

## Deduplication

Node ids are deterministic strings built from internal ids (e.g.
`disease_gene:GENE:000201`, `drug_target:TGT:000501`, `pathway:R-HSA-111`,
`evidence:DRUG:000124:ml`). `_GraphBuilder` keeps nodes/edges in a
dict-by-id, so the same gene/target/pathway referenced by multiple reasons —
or shared by two different candidate drugs in the same top-N graph — collapses
to exactly one node and one edge instead of duplicating them
(`test_node_deduplication_across_candidates`).

## Deterministic construction

No randomness, no timestamp-based id, no hash-order dependency. The same
`(candidates, generation_candidates, explanations)` input, in the same order,
always produces byte-identical `nodes`/`edges` lists — pinned down by
`test_edge_and_node_determinism` and, on the real pipeline, by
`test_real_gbm_top3_graph_deterministic`.

---

## Top-N behavior

```python
from app.services.graph import build_candidate_graph, build_evidence_graph, build_graph_for_disease

# one candidate
graph = build_candidate_graph(ranked_candidate, generation_candidate, explanation=explanation)

# an explicit top-N (already ranked)
graph = build_evidence_graph(ranked.top(3), generation_candidates, explanations=explanations)

# convenience: run the whole pipeline for one disease
graph = build_graph_for_disease("Glioblastoma", top_n=3)   # or top_n=1, top_n=10, ...
```

`top_n` is a plain integer — nothing hardcodes "1, 3, or 10" as the only
valid choices, and nothing builds a graph over the full ~1,430-drug universe
automatically. `EvidenceGraph.drug_id` is set only when the graph covers
exactly one candidate; for top-N it is `None` and `drug_ids` lists all of
them (mirrors `RankedCandidateResult.disease_id`'s single-vs-`None`
convention).

---

## API / service (`app.services.graph`)

| Function | Responsibility |
|---|---|
| `build_evidence_graph(candidates, generation_candidates, *, explanations=None)` | core builder: node/edge construction + dedup + provenance, for any list of already-ranked candidates |
| `build_candidate_graph(candidate, generation_candidate, *, explanation=None)` | convenience: exactly one candidate |
| `build_graph_for_candidates(candidates, *, include_explanations=True, explanation_provider=None)` | convenience: re-derives the `CandidateDrug`s for an already-ranked list (e.g. `ranked_result.top(3)`) |
| `build_graph_for_disease(disease_query, *, top_n=1, use_ml=True, include_explanations=True, explanation_provider=None)` | convenience: runs Levels 2-8 itself (mirrors `fuse_for_disease`/`rank_for_disease`) because it needs the intermediate `CandidateDrug` objects those functions don't expose, then Phase 9 for the top-N, then builds the graph |

`InconsistentGraphInputError` is raised for an empty candidate list, mixed
`disease_id`s, or a `RankedCandidate` with no matching `CandidateDrug` — never
a silent partial graph.

---

## Missing evidence

Handled the same way Phases 7-9 already handle it — **unavailable is not
negative**:

* An unavailable `EvidenceComponent` (e.g. no pathway evidence for this
  candidate) produces **no** `evidence_component` node for it — there is
  nothing to visualize — but every other component is built normally.
* The `ml` component unavailable means **no** `prediction` node and **no**
  `evidence:*:ml` node; gene-target/pathway evidence is unaffected.
* A `CandidateDrug` with no `reasons` at all (shouldn't happen for an actual
  candidate, but handled) produces no `disease_gene`/`drug_target`/`pathway`
  nodes — the disease/drug/score/rank nodes are still built normally.
* No explanation supplied -> no `explanation` node;
  `EvidenceGraphMetadata.includes_explanation` reflects this.

`tests/test_evidence_graph.py` — `test_empty_evidence_handling`,
`test_missing_pathway_evidence_no_crash_no_fake_node`,
`test_missing_ml_evidence_no_crash_no_fake_node` — pin all three down.

---

## GBM demo

```bash
cd backend
python scripts/build_evidence_graph.py                       # Glioblastoma, top 1 (default)
python scripts/build_evidence_graph.py "Alzheimer disease" --top-n 3
```

Real output for Glioblastoma / top 1 (regorafenib, rank 1, score 84.9/100):

```
Nodes: 84   Edges: 146
Node types: {'disease': 1, 'drug': 1, 'disease_gene': 11, 'drug_target': 11,
             'pathway': 53, 'evidence_component': 3, 'prediction': 1,
             'score': 1, 'rank': 1, 'explanation': 1}
Edge types: {'associated_with': 64, 'matched_to': 11, 'has_target': 11,
             'participates_in': 53, 'received': 5, 'ranked': 1, 'explained_by': 1}

  DISEASE GENES -> DRUG TARGETS
    BRAF (HGNC:1097)  ->  Serine/threonine-protein kinase B-raf  [INHIBITOR]
    FGFR1 (HGNC:3688)  ->  Fibroblast growth factor receptor 1  [INHIBITOR]
    KIT (HGNC:6342)  ->  Mast/stem cell growth factor receptor Kit  [INHIBITOR]
    ...
  PATHWAYS
    RAF/MAP kinase cascade  (disease support=22, drug support=4)
    ...
  ML PREDICTION: random_forest prediction (output=0.911551, baseline=0.500294)
  EVIDENCE COMPONENTS
    gene_target evidence: value=0.866667 contribution=39.0 pts
    pathway evidence: value=0.743119 contribution=18.578 pts
    ml evidence: value=0.911551 contribution=27.3465 pts
  AI EXPLANATION (deterministic_fallback)
    regorafenib was computationally prioritized at rank 1 for glioblastoma...
```

Every number above comes straight from the real, already-computed Phase 6-9
output for this candidate — nothing in this file is hardcoded.

---

## Testing

`backend/tests/test_evidence_graph.py` (34 tests): node/edge construction for
every node/edge type, provenance preservation, deduplication (within and
across candidates), determinism, input-validation errors, missing-evidence
handling (empty/pathway/ML), one-candidate vs. top-N graphs, "no dangling
edges" / "only known edge types" fabrication guards, and two real end-to-end
GBM tests (skipped gracefully if Level 1 data isn't ingested locally — same
pattern as the rest of the suite).

---

## Limitations

* This is a **representation** of evidence the pipeline already computed —
  it establishes nothing new, biologically or clinically, and inherits every
  disclaimer from Phases 6-9 (not clinical efficacy, not a treatment
  recommendation).
* No `drug_target -belongs_to-> pathway` edge (see "A deliberate scoping
  decision" above) — Level 4 doesn't carry that specific mapping today; a
  future phase could add it if Level 3's `DrugProfile.biological_context`
  per-pathway `supporting_uniprot_ids` were wired through Level 4.
* `metadata` dicts are intentionally loose (`dict`, not a fully-typed
  sub-schema per node type) so one `GraphNode`/`GraphEdge` shape covers every
  node/edge kind — a future dashboard should treat `metadata` as
  type-dependent, keyed off `node.type`/`edge.type`.
* No graph database, no persistence: `EvidenceGraph` is built fresh per call
  and returned in-memory: exactly what this phase's "no new paid service"
  and "no graph database" constraints require.
