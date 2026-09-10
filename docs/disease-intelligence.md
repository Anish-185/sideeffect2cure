# Level 2 — Disease Intelligence

Level 2 owns exactly this slice of the canonical pipeline:

```
User Disease Query  ->  Disease Resolver  ->  Structured Disease Profile
```

Nothing downstream (candidate drugs, drug profiles, scoring, feature
engineering, ML, fusion, ranking, explainability, LINCS/GDSC/DepMap,
literature, KG, frontend) is implemented here.

> **Language matters.** A gene or pathway is *associated with* a disease — never
> *causes* it. A profile is *potentially relevant* evidence — never
> *therapeutically effective*. SideEffect2Cure AI is a research
> hypothesis-generation tool, not a clinical decision-support system.

---

## Components

| Piece | Module | Role |
|---|---|---|
| `DiseaseRepository` | `app.services.disease.repository` | cached read-only access to the Level 1 disease datasets + lookup indexes + integrity sanitisation |
| `DiseaseResolver` | `app.services.disease.resolver` | user query → exactly one supported disease, or an explicit "cannot resolve" result |
| profile builder | `app.services.disease.profile` | `get_disease_profile`, `build_disease_profile`, `render_summary` |
| schemas | `app.models.disease` | `ResolutionResult`, `DiseaseProfile`, `GeneAssociation`, `PathwayAssociation`, `DiseaseMolecularProfile`, `ProfileProvenance` |
| aliases | `app/data/resources/disease_aliases.tsv` | lexical name synonyms → ontology id (editable, optional) |

All business logic is in `app.services` — the FastAPI route layer is untouched
at this level.

### Public interface

```python
from app.services.disease import resolve_disease, get_disease_profile, build_disease_profile

resolve_disease("Glioblastoma")        # -> ResolutionResult
get_disease_profile("DIS:000035")      # -> DiseaseProfile   (raises UnknownDiseaseError)
build_disease_profile("GBM")           # -> DiseaseProfile   (resolve + build; raises DiseaseResolutionError)
```

Each accepts an optional `repository=` for testing / alternate data.

---

## DiseaseResolver

### Supported query types (first exact match wins)

| # | Query type | Example | `matched_on` |
|---|---|---|---|
| 1 | internal disease id | `DIS:000035` | `internal_id` |
| 2 | ontology id (EFO/MONDO/…) | `MONDO_0018177`, `mondo:0018177` | `ontology_id` |
| 3 | exact disease name | `Glioblastoma` → `glioblastoma` | `exact_name` |
| 4 | lexical alias | `GBM` | `alias` |

Matching is **case-insensitive and whitespace/punctuation-normalized**. Names in
the Level 1 data are stored lower-case, so `disease_name` on results is
lower-case.

### There is no fuzzy matching

An unmatched query returns `status = NOT_SUPPORTED` with advisory
`suggestions` (substring hints) — it is **never** silently resolved to a
"closest" disease. A query that matches more than one disease returns
`status = AMBIGUOUS` with the `candidates` list; the caller must disambiguate
with an internal or ontology id.

### Resolution statuses

| status | meaning |
|---|---|
| `RESOLVED` | exactly one supported disease (`match` populated) |
| `EMPTY_QUERY` | query was empty / whitespace |
| `NOT_SUPPORTED` | no exact match; `suggestions` may hint at near names |
| `AMBIGUOUS` | ≥2 distinct diseases matched; `candidates` populated |

### Aliases

`disease_aliases.tsv` maps lower-cased name synonyms/abbreviations to ontology
ids. It carries **no biological content**. An alias whose ontology target is not
in the ingested `diseases` table is ignored and listed in
`repository.unresolved_aliases` — never invented. GBM is **not** special-cased:
`glioblastoma` resolves by exact name because it is in the dataset; `GBM`
resolves because the alias file lists `gbm → MONDO_0018177` and that disease is
ingested.

---

## DiseaseProfile schema

`DiseaseProfile` (see `app/models/disease.py`) is the canonical structure handed
to every later level:

| field | source |
|---|---|
| `disease_id` | `diseases.disease_id` (internal, `DIS:NNNNNN`) |
| `disease_name` | `diseases.disease_name` (lower-case canonical) |
| `ontology_id` | `diseases.ontology_id` (EFO/MONDO) |
| `external_identifiers[]` | `identifiers` crosswalk (`entity_type == "disease"`) |
| `genes[]` → `GeneAssociation` | `disease_genes` rows, score-descending |
| `pathways[]` → `PathwayAssociation` | `disease_pathways` rows, support-descending |
| `molecular_profile` → `DiseaseMolecularProfile` | deterministic rollup of the above |
| `provenance` → `ProfileProvenance` | source + limitations of every part |
| `summary_text` | deterministic plain-text summary (no LLM) |

### GeneAssociation

`gene_id` (internal `GENE:NNNNNN`), `gene_name` (approved symbol, e.g. `TP53`),
`ensembl_id`, `association_score` (Open Targets overall score, **[0, 1]**),
`source` (`opentargets`).

**Provenance / semantics:** the score quantifies how strongly a gene is
*associated with* the disease across Open Targets evidence types. It does **not**
mean the gene causes the disease, nor that modulating it is therapeutically
useful. Level 1 kept only the **top 200** associations per disease
(`provenance.genes_capped_per_disease`); `provenance.genes_truncated` is `true`
when a disease hit that cap (all 39 currently do).

### PathwayAssociation

`pathway_id` (internal `PATH:NNNNNN`), `pathway_name`, `reactome_id`
(`R-HSA-…`), `gene_support_count`, `association_score`, `source`
(`derived:opentargets+reactome`).

**Provenance — this is a DERIVED table, not curated:**

```
disease's associated genes  ->  Reactome Ensembl2Reactome (human) gene→pathway
                            ->  keep (disease, pathway) with ≥ 3 supporting genes
```

`gene_support_count` is that gene overlap; `association_score` is the **mean**
Open Targets score of the supporting genes. These are *candidate pathways of
interest*, **not** independent disease–pathway assertions and **not** pathway
enrichment statistics with p-values.

### DiseaseMolecularProfile

A compact Disease → genes → pathways rollup (`gene_count`, `pathway_count`,
`mean`/`max` gene association score, top-15 gene symbols and pathway names,
`genes_truncated`). It is **not** a gene-expression signature, drug-response
matrix, or molecular embedding — those are later evidence layers.

---

## Error handling

| condition | behaviour |
|---|---|
| empty query | `ResolutionResult(status=EMPTY_QUERY)` |
| unknown disease name | `ResolutionResult(status=NOT_SUPPORTED)` (+ suggestions) |
| ambiguous name | `ResolutionResult(status=AMBIGUOUS)` (+ candidates) |
| invalid internal/ontology id | `ResolutionResult(status=NOT_SUPPORTED)` |
| `get_disease_profile` with bad id | raises `UnknownDiseaseError` |
| `build_disease_profile` unresolvable | raises `DiseaseResolutionError` (carries the `ResolutionResult`) |
| processed data missing | raises `DatasetsNotBuilt` (from Level 1 loaders) |
| malformed / orphan rows in data | dropped deterministically; recorded in `repository.integrity_issues` |

The resolver never returns an unrelated disease.

---

## Caching / performance

The disease tables are tiny (39 diseases, ~7.8k gene rows, ~7.1k pathway rows).
`DiseaseRepository` loads them once via the Level 1 loaders and indexes them
with plain dicts. `default_repository()` is a process-wide
`functools.cache` singleton (`reset_default_repository()` clears it after
re-ingestion). No database, no external cache.

---

## Example — Glioblastoma

```python
>>> from app.services.disease import build_disease_profile
>>> p = build_disease_profile("Glioblastoma")
>>> p.disease_id, p.disease_name, p.ontology_id
('DIS:000035', 'glioblastoma', 'MONDO_0018177')
>>> [g.gene_name for g in p.genes[:5]]
['TP53', 'IDH1', 'EGFR', 'PTEN', 'BRAF']
>>> len(p.genes), len(p.pathways)
(200, 346)
>>> p.molecular_profile.genes_truncated
True
>>> print(p.summary_text)
Disease: glioblastoma
Internal ID: DIS:000035
Ontology ID: MONDO_0018177

Associated genes (200, Level 1 cap reached):
  TP53, IDH1, EGFR, PTEN, BRAF, ATRX, RB1, NF1, PIK3CA, PIK3R1 ...

Associated pathways (346, derived from disease genes x Reactome):
  - Ub-specific processing proteases (n=23)
  - RAF/MAP kinase cascade (n=22)
  ...

Evidence:
  - disease-gene associations: Open Targets Platform association scores
  - disease-pathway associations: DERIVED (Reactome gene->pathway; >= 3 supporting genes), not curated

Note: 'associated with' does not mean 'causes'. This profile is
hypothesis-generating evidence, not a clinical or therapeutic claim.
```

`GBM` and `MONDO_0018177` resolve to the same profile.

---

## Limitations

- **Disease scope** = the 39 diseases ingested in Level 1 (`disease_seed.tsv`).
  Anything else is `NOT_SUPPORTED`. Widen scope by editing the Level 1 seed and
  re-ingesting.
- Disease names are lower-case (Level 1 normalization).
- Genes are capped at top-200/disease (Open Targets overall score); the profile
  is not the complete association set for any disease.
- `disease_pathways` is derived, coarse, and thresholded at ≥3 genes — treat as
  a hint, not a pathway-enrichment analysis.
- No aliases beyond the small hand-curated lexical file; no ontology
  cross-references beyond what Level 1 stored (currently just the primary
  MONDO id per disease).
- No synonym expansion from external ontology services (would be a Level 1
  ingestion concern, not Level 2).

---

## What remains for Level 3

Level 3 begins **Candidate Drug Generation**: given a `DiseaseProfile`, produce
an initial candidate set of existing drugs to score — e.g. drugs whose targets
intersect the disease's associated genes, or drugs sharing disease pathways —
followed by the **Drug Profile** (targets + side effects + mechanisms) for each
candidate. No scoring, ranking, ML, or fusion yet.
