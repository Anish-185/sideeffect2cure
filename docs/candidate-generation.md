# Level 4 — Candidate Drug Generation

Level 4 owns exactly this slice of the canonical pipeline:

```
DiseaseProfile  ->  Candidate Drug Generation  ->  candidate drug set
```

It does **not** score, rank, predict, fuse evidence, or explain. Its only job
is to reduce the 1,430-drug universe to the drugs that have a **real biological
relationship** to a disease and therefore *deserve downstream analysis*.

> **Candidate generation ≠ therapeutic recommendation.**
> A candidate is a drug with a relationship worth investigating. It is not a
> claim of efficacy, and it carries **no score, probability or ranking** at this
> level. SideEffect2Cure AI is a research hypothesis-generation tool.

---

## Architecture

```
DiseaseProfile (Level 2)
├── genes    (ensembl_id, symbol, association_score, ...)
└── pathways (reactome_id, gene_support_count, ...)
        │
        ├─────────────── gene-target route ───────────────┐
        │   disease gene  ==(HGNC id)==  drug target       │
        │                                                  │
        └─────────────── pathway route ───────────────────┤
            disease Reactome pathway  ==  drug Reactome pathway
                                                           │
                                                     UNION (dedup drug,
                                                     keep every reason)
                                                           │
                                              CandidateGenerationResult
```

| Piece | Module |
|---|---|
| `HGNCBridge` | `app.services.candidates.bridge` — `ensembl_gene_id` / `uniprot` → `hgnc_id` |
| `CandidateIndex` | `app.services.candidates.repository` — reverse indexes (built once) |
| generator | `app.services.candidates.generator` — `generate_candidates(...)` etc. |
| schemas | `app.models.candidate` |

Business logic is in `app.services` — FastAPI routes are untouched.

### Public interface

```python
from app.services.candidates import generate_candidates
from app.services.disease import build_disease_profile

profile = build_disease_profile("Glioblastoma")
result  = generate_candidates(profile)          # -> CandidateGenerationResult

# route-specific (optional):
from app.services.candidates import (
    generate_candidates_by_gene_target, generate_candidates_by_pathway,
)
generate_candidates_by_gene_target(profile)      # -> list[CandidateDrug]
generate_candidates_by_pathway(profile)          # -> list[CandidateDrug]
```

All accept `index=` for tests / alternate data.

---

## Gene-target route

**Signal:** a disease-associated gene and a drug target are the *same gene*.

The two sides use different identifier systems:

| side | source | gene identity |
|---|---|---|
| disease gene | Open Targets (`disease_genes`) | **Ensembl gene id** (`ENSG…`) |
| drug target | ChEMBL (`drug_targets`) | **UniProt accession** (`P…`) |

They are bridged through the **HGNC complete set** (`hgnc_complete_set.txt`,
public domain), which for every human gene lists `hgnc_id`, approved `symbol`,
`ensembl_gene_id` and `uniprot_ids`. Level 4 derives only two maps from it:

```
ensembl_gene_id   -> hgnc_id
uniprot accession -> hgnc_id
```

and candidates **join on `hgnc_id`** — a pure identifier match. No gene-name
string matching. Nothing is invented: an id that HGNC does not map simply
produces no gene-target candidate. Coverage in the current data: 3,115 / 3,123
distinct disease genes and 430 / 509 drug-target rows (173 distinct target
proteins) bridge to an HGNC id.

A drug enters the pool via this route if **≥ 1** of its targets shares an HGNC
id with **≥ 1** disease gene. Each such pairing is stored as a
`GeneTargetMatch` reason:

```
hgnc_id, gene_symbol,
disease_gene_id, disease_gene_ensembl_id, disease_gene_source (opentargets),
drug_target_id, drug_target_name, drug_target_uniprot_id, drug_action_type,
drug_target_source (chembl)
```

If the HGNC file is neither cached nor downloadable the route is reported
unavailable (`provenance.gene_target_bridge_available == false`) and the pathway
route still runs.

---

## Pathway route

**Signal:** the disease and the drug share a Reactome pathway.

| side | source | pathway id |
|---|---|---|
| disease pathway | Level 2 `disease_pathways` (`derived:opentargets+reactome`) | Reactome stable id (`R-HSA-…`) |
| drug pathway | Level 3 Reactome enrichment (`derived:chembl-targets+reactome`) | Reactome stable id |

Both are Reactome stable ids, so the match is a **direct identifier
intersection** — no similarity metric, no threshold. The drug-pathway set is the
**uncapped** output of the Level 3 `ReactomeUniProtIndex` (drug target UniProt →
Reactome, human).

A drug enters via this route if **≥ 1** of its Reactome pathways is also one of
the disease's Reactome pathways. Each match is stored as a `PathwayMatch`:

```
reactome_id, pathway_name,
disease_pathway_id, disease_pathway_source, disease_gene_support_count,
drug_pathway_source, drug_supporting_target_count
```

This route is looser than gene-target (a shared kinase-signalling pathway is a
weaker connection than a shared target) — that is expected. Level 4 does not
judge strength; Level 5 will.

---

## Candidate union

The final pool is `gene_target ∪ pathway`, **deduplicated by `drug_id`**. A drug
reached by both routes appears **once**, with **all** of its reasons (both
`GeneTargetMatch` and `PathwayMatch` entries) preserved — this is what Level 5
needs to compute features and Level 8 needs to explain.

`CandidateDrug` also carries deduplicated convenience roll-ups:
`matched_gene_hgnc_ids`, `matched_gene_symbols`, `matched_disease_gene_ids`,
`matched_drug_target_ids`, `matched_pathway_reactome_ids`.

---

## Candidate record schema (`app.models.candidate`)

```
CandidateGenerationResult
├── disease_id, disease_name, ontology_id
├── candidate_count
├── candidates: list[CandidateDrug]
│     ├── drug_id, drug_name, disease_id, disease_name
│     ├── methods: [gene_target | pathway]           (distinct, sorted)
│     ├── reasons: list[CandidateGenerationReason]   (every route hit)
│     │     ├── method
│     │     ├── gene_target: GeneTargetMatch | None
│     │     └── pathway:     PathwayMatch     | None
│     └── matched_* roll-ups
├── counts_by_method: {gene_target, pathway, gene_target_only, pathway_only, both, universe}
└── provenance: CandidateGenerationProvenance
      ├── gene_target_bridge (+ available / unavailable_reason)
      ├── pathway_disease_source, pathway_drug_source (+ available / reason)
      ├── datasets_used, methods_run
      ├── disclaimer
      └── interpretation_note  ("worth downstream analysis, NOT a recommendation")
```

**No** `score` / `probability` / `confidence` / `rank` / `weight` / `similarity`
field exists on any of these models — by design and enforced by a test.
`gene_support_count` and `supporting_target_count` are **counts carried
through** from Levels 2/3 as provenance, not scores.

---

## Provenance

Every reason is traceable to its origin:

| reason | disease side | drug side |
|---|---|---|
| `GENE_TARGET` | Open Targets disease-gene association + HGNC id | ChEMBL drug-target (mechanism of action) + HGNC id |
| `PATHWAY` | Level 2 derived disease pathway (Open Targets genes × Reactome) | Level 3 Reactome enrichment (ChEMBL target UniProt × Reactome) |

Sources are never merged in a way that loses attribution — each `GeneTargetMatch`
/ `PathwayMatch` keeps both the disease-side and drug-side source strings.

---

## Candidate set size

Inclusion is **purely relationship-driven** — there is no top-K, no threshold to
tune. For **Glioblastoma** (`MONDO_0018177`) against the current data:

```
universe                 1430
gene-target candidates     19
pathway candidates        131
  gene-target only          1
  pathway only            113
  both                     18
UNION (candidate_count)   132     (~9% of the universe)
```

If this pool ever looks pathological the fix is to investigate the underlying
relationships (Level 1 coverage, Level 2 pathway derivation), not to add an
artificial cutoff.

---

## Side effects are deliberately NOT used here

SIDER side effects are **not** a candidate-generation signal at Level 4. No
side-effect similarity, no disease–side-effect links, no embeddings. Side
effects may be considered later as *features / evidence*, not as a gate.

---

## Determinism

No LLM, no embeddings API, no semantic search, no paid service. Generation is
dict lookups over locally-cached structured data. `CandidateIndex` is built once
(`default_index()`, a `functools.cache` singleton) from `drug_targets` + the
HGNC bridge + the Level 3 Reactome index:

```
hgnc_id      -> [drug target rows]      (gene-target route)
reactome_id  -> {drug_id}               (pathway route)
drug_id      -> {reactome_id: meta}     (fills the match record)
```

so generation is `O(#disease genes + #disease pathways)`, never a scan of 1,430
drugs. No database, vector store or graph store.

---

## Limitations

- **Gene-target route** only covers targets that (a) exist in the SIDER∩ChEMBL
  mechanism-of-action set (Level 3 caveat) and (b) bridge to an HGNC id
  (173 / 215 distinct target proteins). Non-human / obsolete accessions drop out.
- **Pathway route** is coarse by construction — a shared broad signalling
  pathway is enough to enter the pool. Expect it to dominate the count.
- Disease genes are the Level 1 top-200-per-disease cap; a target of a lower
  disease gene will not generate a gene-target candidate.
- Both routes require their external file (HGNC / Reactome); each degrades
  independently and is reported in `provenance`.
- The candidate set is not exhaustive drug-repurposing space — it is the subset
  reachable through *these two* relationship types.

---

## What Level 5 will build

**Feature Engineering.** Level 5 pairs each `CandidateDrug` with the full
Level 3 `DrugProfile` and the Level 2 `DiseaseProfile` and computes numeric
features over the pair (e.g. counts / overlaps / action-type composition /
side-effect burden) — still **no** ML, similarity score, or repurposing score;
those are Level 6+.
