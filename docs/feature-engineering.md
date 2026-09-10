# Level 5 — Feature Engineering

Level 5 owns exactly this slice of the canonical pipeline:

```
CandidateDrug + DiseaseProfile + DrugProfile  ->  FeatureVector
```

It does **not** train, predict, score, fuse evidence, rank, or explain. Its only
job is to turn each disease-drug candidate pair into a **deterministic,
descriptive** feature vector for Level 6 to consume.

> **Features describe evidence — they do not decide the answer.**
> There is no `repurposing_score`, `probability`, `confidence`, `rank`, or
> `similarity` field anywhere in this level. Nothing here implies treatment
> efficacy. SideEffect2Cure AI is a research hypothesis-generation tool.

---

## Architecture

```
DiseaseProfile (L2)   CandidateDrug (L4)   DrugProfile (L3)
        \                    |                   /
         \                   |                  /
          +----- build_feature_vector(...) -----+
                          |
                     FeatureVector          (typed; .to_feature_dict() -> flat)
```

| Piece | Module |
|---|---|
| `FeatureVector`, `FeatureVectorMetadata` | `app.models.feature` |
| builder | `app.services.features.builder` |

Business logic is in `app.services` — FastAPI routes are untouched.

### Public interface

```python
from app.services.features import build_feature_vector, build_feature_vectors, feature_rows

# one pair
fv = build_feature_vector(candidate, disease_profile, drug_profile, index=...)
build_features(candidate, disease_profile, drug_profile)          # alias

# batch (reuses one CandidateIndex, builds each DrugProfile once)
vectors = build_feature_vectors(disease_profile, candidates, index=...)
rows    = feature_rows(vectors)      # list[dict], id-tagged flat features for a DataFrame
fv.to_feature_dict()                 # flat {name: number|bool|None}, no identity/metadata
```

`index` defaults to the Level 4 `default_index()` (HGNC bridge + Reactome index +
drug repo). It is the **only** thing Level 5 loads — no new data or identifier
mappings.

---

## FeatureVector schema

Identity: `disease_id`, `drug_id`, `disease_name`, `drug_name`.

### A. Candidate-generation features (from `CandidateDrug`)

| feature | type | meaning |
|---|---|---|
| `generated_by_gene_target` | bool | Level 4 produced this candidate via the gene-target route |
| `generated_by_pathway` | bool | … via the pathway route |
| `generation_method_count` | int | 1 or 2 |
| `gene_target_reason_count` | int | number of `GeneTargetMatch` reasons on the candidate |
| `pathway_reason_count` | int | number of `PathwayMatch` reasons |

### B. Disease-gene / drug-target overlap (HGNC id join)

Disease genes (Ensembl) and drug targets (UniProt) are mapped to `hgnc_id` with
the **Level 4 HGNC bridge** — no gene-name string matching, no new mapping.

| feature | type | meaning |
|---|---|---|
| `disease_gene_count` | int | genes on the DiseaseProfile (Level 1 top-N-per-disease cap) |
| `disease_gene_hgnc_mapped_count` | int | of those, how many resolve to an HGNC id |
| `drug_target_count` | int | distinct drug targets on the DrugProfile |
| `drug_target_hgnc_mapped_count` | int | of those, how many resolve to an HGNC id |
| `matched_gene_target_count` | int | distinct HGNC genes present on **both** sides |
| `matched_disease_gene_count` | int | distinct disease gene ids whose HGNC is matched |
| `matched_drug_target_count` | int | distinct drug target ids whose HGNC is matched |
| `fraction_of_drug_targets_matching_disease_genes` | float \| None | `matched_gene_target_count / drug_target_hgnc_mapped_count` |
| `fraction_of_disease_genes_targeted_by_drug` | float \| None | `matched_gene_target_count / disease_gene_hgnc_mapped_count` |

### C. Pathway overlap (direct Reactome id intersection)

Both sets are Reactome stable ids. The drug's set is the **uncapped** Level 4
index set (`drug_pathway_source == "level4_index_uncapped"`); if the index has no
pathway data it falls back to the DrugProfile's `biological_context.pathways`
(capped at 100 — flagged as `drug_profile_capped_100`), else `unavailable`.

| feature | type | meaning |
|---|---|---|
| `disease_pathway_count` | int | distinct Reactome ids on the DiseaseProfile |
| `drug_pathway_count` | int | distinct Reactome ids reached via the drug's targets |
| `matched_pathway_count` | int | size of the intersection |
| `fraction_of_drug_pathways_matching_disease_pathways` | float \| None | `matched_pathway_count / drug_pathway_count` |
| `fraction_of_disease_pathways_matching_drug_pathways` | float \| None | `matched_pathway_count / disease_pathway_count` |

### D. Side-effect features

| feature | type | meaning |
|---|---|---|
| `side_effect_count` | int | number of SIDER side effects on the DrugProfile |

Only the drug's side-effect **burden** is represented. **No** disease-side-effect
association is invented, no semantic similarity, no embeddings.

### E. Target / action-type features

| feature | type | meaning |
|---|---|---|
| `unique_target_count` | int | distinct drug targets (= `drug_target_count`) |
| `inhibitor_target_count` / `agonist_target_count` / `antagonist_target_count` | int | targets with that ChEMBL `action_type` |
| `targets_with_action_type_count` / `targets_missing_action_type_count` | int | coverage of `action_type` |
| `target_action_type_counts` | dict[str,int] | **full** breakdown — only action types present in the data |
| `target_type_counts` | dict[str,int] | **full** breakdown — only target types present in the data |

Action / target types are taken verbatim from ChEMBL — none are invented, and an
action type is **not** interpreted as therapeutic benefit.

### F. Drug-level structural counts

| feature | type | meaning |
|---|---|---|
| `mechanism_count` | int | number of `MechanismOfAction` entries on the DrugProfile |

(`drug_target_count`, `drug_pathway_count`, `side_effect_count` above also serve
as drug-level structural counts.)

### G. Evidence-source availability flags

Booleans indicating **which sources contributed**, not a confidence score:

`has_sider_evidence`, `has_chembl_target_evidence`, `has_reactome_pathway_evidence`,
`has_gene_target_bridge`, `disease_pathways_available`.

### Metadata (`FeatureVectorMetadata`)

`feature_schema_version` (`"1.0"`), `gene_target_bridge` / `pathway_intersection`
descriptions, `drug_pathway_source`, `ratio_denominators` (formula per fraction),
`unavailable` (feature groups with no source this run), `leakage_guard`,
`disclaimer`.

---

## Ratio formulas & denominator handling

```
fraction_of_drug_targets_matching_disease_genes   = matched_gene_target_count / drug_target_hgnc_mapped_count
fraction_of_disease_genes_targeted_by_drug        = matched_gene_target_count / disease_gene_hgnc_mapped_count
fraction_of_drug_pathways_matching_disease_pathways = matched_pathway_count   / drug_pathway_count
fraction_of_disease_pathways_matching_drug_pathways = matched_pathway_count   / disease_pathway_count
```

- **Denominator is zero → the fraction is `None`.** Never `NaN`, never `inf`,
  never a division error. (`app.services.features.builder._ratio`.)
- Numerator ⊆ denominator by construction, so every non-null fraction is in
  `[0, 1]`.
- The gene fractions use the **HGNC-mapped** counts as denominators (a
  non-bridgeable target/gene cannot match anything), and the mapped counts are
  exposed separately so Level 6 can recompute against raw counts if it wants.

---

## Numerical safety

Handled explicitly and covered by tests: zero disease genes, zero disease
pathways, zero drug targets, zero drug pathways, missing Reactome enrichment,
missing HGNC bridge, missing `action_type`, empty candidate reasons. In every
case the affected features are `0` / `None` with a flag in `metadata.unavailable`
— the vector is always well-formed.

---

## Data-leakage precautions

Feature computation reads **only**:

- the Level 2 `DiseaseProfile` (genes, pathways, provenance),
- the Level 3 `DrugProfile` (side effects, targets, mechanisms, pathway context),
- the Level 4 `CandidateDrug` (generation methods + reasons),
- the Level 4 `CandidateIndex` (HGNC bridge, uncapped drug-pathway sets).

It does **not** use — and there is no code path to — ML predictions, repurposing
labels, ranking outputs, manually assigned success/failure labels, or any
therapeutic-outcome information. `FeatureVectorMetadata.leakage_guard` states this
on every vector.

---

## Determinism & performance

Same inputs → byte-identical `FeatureVector` (tested). No randomness, no LLM, no
embeddings API, no network at feature-build time, no paid service. Batch mode
builds one `CandidateIndex` and one `DrugProfile` per candidate
(`enrich_pathways=False` — pathways come from the index), so 132 GBM candidates
produce 132 vectors in ~3 s.

---

## GBM sanity check (`build_disease_profile("Glioblastoma")` → generate → features)

```
132 feature vectors  (disease genes 200, disease pathways 346)
drug_pathway_source: level4_index_uncapped

carmustine (bcnu)  [gene_target only]
  matched_gene_target_count = 1   (GSR)   drug_target_count = 3   drug_target_hgnc_mapped_count = 1
  fraction_of_drug_targets_matching_disease_genes = 1.0
  fraction_of_disease_genes_targeted_by_drug      = 0.005
  drug_pathway_count = 0  matched_pathway_count = 0
  fraction_of_drug_pathways_matching_disease_pathways = None   <- zero denominator
  side_effect_count = 163   inhibitor_target_count = 3   mechanism_count = 3
  has_reactome_pathway_evidence = False

6-thioguanine  [pathway only]
  matched_gene_target_count = 0   matched_pathway_count = 2
  fraction_of_drug_pathways_matching_disease_pathways = 0.5   (2 of 4)
  drug_target_count = 2   drug_target_hgnc_mapped_count = 1
```

Values are derived from real project data — none are hardcoded; the tests check
invariants (matched ≤ available, fractions ∈ [0,1] ∪ {None}, disease-specificity),
not fixed numbers.

---

## Limitations

- Gene-target features inherit the Level 4 coverage limits (SIDER∩ChEMBL targets;
  173 / 215 target proteins bridge to HGNC; disease genes capped at 200).
- Pathway features are counts of a *direct id intersection* — no notion of
  pathway size, specificity, or hierarchy.
- `side_effect_count` is raw burden; it carries **no** disease relevance.
- `target_action_type_counts` / `target_type_counts` are variable-key dicts;
  Level 6 must decide how to encode sparse columns (`feature_rows` flattens them
  with `action_type__` / `target_type__` prefixes as a starting point).
- The feature set is intentionally small and interpretable — it is not an
  exhaustive descriptor of disease-drug biology.

---

## What Level 6 will build

**ML Prediction.** Level 6 takes the `FeatureVector`s (via `feature_rows` /
`to_feature_dict`), assembles a matrix, and trains / applies a lightweight,
interpretable model to produce a per-candidate model output — the first place a
numeric per-drug value appears. Evidence fusion, ranking and explainability are
Level 7+.
