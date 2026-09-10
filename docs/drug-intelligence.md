# Level 3 — Drug Intelligence

Level 3 owns exactly this slice of the canonical pipeline:

```
Drug Query  ->  Drug Resolver  ->  Structured DrugProfile
```

Nothing downstream (candidate generation, drug–disease matching, scoring,
target/pathway/side-effect similarity, feature engineering, ML, fusion, ranking,
explainability, LINCS/GDSC/DepMap, literature, frontend) is implemented here.

> **Language matters.** A drug *acts on* a target and its targets *map to*
> pathways — this is mechanistic / annotation evidence. It is **never** a claim
> that the drug treats, or is clinically effective for, any disease.
> SideEffect2Cure AI is a research hypothesis-generation tool.

> **Sources were chosen by usefulness, not completeness.** An external source is
> integrated only if it adds information we lack, is simple and reliable, and is
> free. See §"Optional sources" — only **one** optional source (Reactome) met
> the bar.

---

## Components

| Piece | Module | Role |
|---|---|---|
| `DrugRepository` | `app.services.drug.repository` | cached read-only access to `drugs` / `drug_side_effects` / `drug_targets` / `identifiers`, lookup indexes, integrity sanitisation |
| `DrugResolver` | `app.services.drug.resolver` | query → exactly one supported drug, or an explicit "cannot resolve" result |
| enrichment | `app.services.drug.enrichment` | optional Reactome `UniProt → pathway` index (best-effort) |
| profile builder | `app.services.drug.profile` | `get_drug_profile`, `build_drug_profile`, `render_summary` |
| schemas | `app.models.drug` | `DrugResolutionResult`, `DrugProfile`, `SideEffect`, `DrugTargetAssociation`, `MechanismOfAction`, `PathwayContext`, `DrugBiologicalContext`, `DrugProvenance` |

Business logic is in `app.services` — FastAPI routes are untouched.

### Public interface

```python
from app.services.drug import resolve_drug, get_drug_profile, build_drug_profile

resolve_drug("Aspirin")               # -> DrugResolutionResult
get_drug_profile("DRUG:000124")       # -> DrugProfile   (raises UnknownDrugError)
build_drug_profile("CHEMBL25")        # -> DrugProfile   (resolve + build; raises DrugResolutionError)
```

Each accepts `repository=` (for tests / alternate data) and
`enrich_pathways=` / `pathway_index=` (to disable or inject the optional
Reactome step).

---

## DrugResolver

### Supported query types (first exact match wins)

| # | Query type | Example | `matched_on` |
|---|---|---|---|
| 1 | internal drug id | `DRUG:000124` | `internal_id` |
| 2 | external identifier | `CHEMBL25`, `2244`, `CID:2244` | `external_id` |
| 3 | exact drug name | `Aspirin` → `aspirin` | `exact_name` |

Case-insensitive, whitespace/punctuation-normalized. Names in the Level 1 data
are lower-case. **No fuzzy matching** — an unmatched query returns
`NOT_SUPPORTED` (with advisory `suggestions`), never a "closest" drug.

### Ambiguity is real for drug names

SIDER carries **86 drug names shared by ≥2 compounds** (different salts /
stereoisomers / PubChem CIDs — e.g. `amlodipine`, `betamethasone`, `adefovir`).
A name query for one of these returns `status = AMBIGUOUS` with the `candidates`
list; the caller disambiguates with an internal id (`DRUG:…`) or a ChEMBL /
PubChem id. The resolver never picks one arbitrarily.

There is **no drug alias / synonym file** — brand names and chemical synonyms
are a large, messy space and none of the current queries need them. If added
later it would be a Level 1 ingestion concern (synonyms attached to the `drugs`
table), not a Level 3 hard-coded map.

### Resolution statuses

`RESOLVED` · `EMPTY_QUERY` · `NOT_SUPPORTED` (+`suggestions`) ·
`AMBIGUOUS` (+`candidates`).

---

## DrugProfile schema

```
DrugProfile
├── identity     drug_id, drug_name, canonical_identifier, chembl_id, pubchem_cid,
│                external_identifiers[]  (from the Level 1 crosswalk)
├── side_effects[]  -> SideEffect            (SIDER)
├── targets[]       -> DrugTargetAssociation (ChEMBL mechanism of action)
├── mechanisms[]    -> MechanismOfAction     (derived: action_type + target_name)
├── biological_context -> DrugBiologicalContext   (OPTIONAL)
│      ├── proteins[]   UniProt accessions from the drug's targets
│      └── pathways[]   -> PathwayContext    (derived: target UniProt -> Reactome)
├── provenance  -> DrugProvenance
└── summary_text   deterministic plain-text (no LLM)
```

### SideEffect  (source: SIDER)

`side_effect_id` (internal `SE:NNNNNN`), `side_effect_name` (lower-case),
`umls_cui` (UMLS/MedDRA concept id), `source`.

### DrugTargetAssociation  (source: ChEMBL)

`target_id` (internal `TGT:NNNNNN`), `target_name`, `target_type`
(e.g. `SINGLE PROTEIN`), `uniprot_id` (UniProt accession — carried by Level 1
from ChEMBL `target_components`), `action_type` (e.g. `INHIBITOR`), `source`.

**Coverage limitation (documented, not hidden):** targets come from ChEMBL
**curated mechanism-of-action** records, restricted at Level 1 to the
**SIDER ∩ ChEMBL** intersection — 548 drug–target rows across ~390 of the 1,430
drugs. This is **not** the full set of ChEMBL bioactivity targets for a drug,
and a drug with no `targets` row is **not** necessarily target-less.

### MechanismOfAction  (derived from ChEMBL fields)

`target_id`, `target_name`, `action_type`, `description` (deterministic phrase,
e.g. `"inhibitor of Cyclooxygenase"`), `source`. The free-text ChEMBL MoA
string is **not** in the Level 1 processed layer, so it is not claimed here —
mechanism is represented as `(action_type, target)` pairs.

### PathwayContext  (OPTIONAL, source: Reactome — derived)

`reactome_id` (`R-HSA-…`), `pathway_name`, `supporting_target_count`,
`supporting_uniprot_ids[]`, `source = "derived:chembl-targets+reactome"`.

**Derivation:** `drug → ChEMBL target → UniProt accession → Reactome`
(`UniProt2Reactome.txt`, human only). `supporting_target_count` is how many of
the drug's targets map into that pathway. **Not** a curated drug–pathway
assertion and **not** a pathway-enrichment statistic.

`DrugBiologicalContext.pathway_context_available` is `false` when the Reactome
file is not cached and cannot be downloaded, or when the drug has no UniProt
target — and `unavailable_reason` explains which. **The core profile
(identity / side effects / targets / mechanisms) is unaffected.**

---

## Optional sources — decision log

The brief's rule: integrate a source only if it *adds information we lack* **and**
is *simple and reliable* **and** is *free*. Applied:

| Source | Decision | Why |
|---|---|---|
| **Reactome** | ✅ **integrated** (optional context) | Adds the one thing Level 1 lacks for drugs — a pathway footprint — that later levels need to compare against Level 2's disease pathways. Reuses a source Level 1 already integrated (CC0); one extra flat file (`UniProt2Reactome.txt`), cached locally; a plain `UniProt → pathway` join off `drug_targets.uniprot_id`. Kept strictly optional. |
| **PubChem** | ❌ not extended | Level 1 already maps every drug to a PubChem CID (and uses PubChem for CID↔ChEMBL). Extra chemical descriptors (SMILES/InChI/formula/logP) have **no consumer** in the current pipeline (no structure similarity, no embeddings). The brief explicitly says not to add descriptors "simply because they are available." |
| **UniProt** | ❌ not called live | UniProt accessions are **already on the ChEMBL targets** (`drug_targets.uniprot_id`, 509/548 rows) and in the crosswalk (1,341 target xrefs). ChEMBL already gives target name + type. A live UniProt annotation call per target adds a fetch/cache/normalize burden for marginal naming polish — the existing representation is sufficient for the prototype. |
| **Open Targets** | ❌ skipped | Its drug-level value is **indications / known-drug disease links** — that is Level 4+ (candidate generation & scoring), explicitly out of scope here. Its mechanism-of-action data duplicates ChEMBL. Nothing left that belongs at the DrugProfile stage. |

Net: **1 of 4** optional sources integrated. This is recorded per-profile in
`provenance.optional_sources_used` and `provenance.optional_sources_skipped`.

---

## Identifier strategy

Reuses the Level 1 crosswalk unchanged. A drug carries:

- internal `drug_id` (`DRUG:NNNNNN`) — the join key for all levels;
- `chembl_id` (957/1,430 drugs) — link to ChEMBL, targets, mechanisms;
- `pubchem_cid` (1,430/1,430) — primary chemical identity;
- `canonical_identifier` — ChEMBL id if known, else `CID:<cid>`.

`external_identifiers[]` on the profile is the full crosswalk view
(`entity_type == "drug"`), each row tagged with its `source`.

Targets carry `uniprot_id` (the stable protein handle used for the Reactome
step and available to later levels).

---

## Provenance

Every field is traceable:

| field | source |
|---|---|
| identity / ids | `drugs` + `identifiers` (SIDER, PubChem, ChEMBL) |
| `side_effects` | SIDER 4.1 (`drug_side_effects`) |
| `targets` | ChEMBL mechanism of action (`drug_targets`) |
| `mechanisms` | ChEMBL `action_type` + `target_name` |
| `biological_context.proteins` | UniProt accessions from ChEMBL targets |
| `biological_context.pathways` | Reactome `UniProt2Reactome` (human) |

Sources are never merged in a way that loses attribution — each list element
carries its own `source`, and `DrugProvenance` records what was and wasn't used.

---

## Error handling

| condition | behaviour |
|---|---|
| empty query | `DrugResolutionResult(status=EMPTY_QUERY)` |
| unknown name | `NOT_SUPPORTED` (+ suggestions) |
| ambiguous name | `AMBIGUOUS` (+ candidates) |
| invalid internal / external id | `NOT_SUPPORTED` |
| `get_drug_profile` bad id | raises `UnknownDrugError` |
| `build_drug_profile` unresolvable | raises `DrugResolutionError` (carries the result) |
| processed data missing | raises `DatasetsNotBuilt` (Level 1 loaders) |
| malformed / orphan rows | dropped deterministically; in `repository.integrity_issues` |
| Reactome file unreachable | `pathway_context_available = False`; core profile still built |

---

## Performance

No database, no vector/graph store, no paid API. The drug tables are small
(1,430 drugs, 145k side-effect rows, 548 target rows) and load once via the
Level 1 loaders into dict indexes. The one external file (`UniProt2Reactome.txt`,
~43 MB, ~55k human rows) is downloaded **once**, cached under
`data/raw/reactome/`, parsed to an in-memory `UniProt → pathway` dict, and
memoised for the process. Nothing here calls a live API at profile-build time,
so the eventual frontend never depends on external services being up.

---

## Example — Aspirin

```python
>>> from app.services.drug import build_drug_profile
>>> p = build_drug_profile("Aspirin")
>>> p.drug_id, p.drug_name, p.chembl_id, p.pubchem_cid
('DRUG:000124', 'aspirin', 'CHEMBL25', '2244')
>>> p.side_effect_count
70
>>> [(t.target_name, t.action_type, t.uniprot_id) for t in p.targets]
[('Cyclooxygenase', 'INHIBITOR', 'P35354')]
>>> [m.description for m in p.mechanisms]
['inhibitor of Cyclooxygenase']
>>> p.biological_context.pathway_context_available
True
>>> [pw.pathway_name for pw in p.biological_context.pathways][:3]
['Synthesis of Prostaglandins (PG) and Thromboxanes (TX)', 'Interleukin-10 signaling', ...]
```

`aspirin`, `CHEMBL25`, `2244`, `CID:2244` and `DRUG:000124` all produce the
same profile.

---

## Known coverage limitations

- **Drug scope** = the 1,430 SIDER compounds ingested in Level 1. Anything else
  is `NOT_SUPPORTED`.
- **Targets/mechanisms** cover only the SIDER ∩ ChEMBL mechanism-of-action
  intersection (~390 drugs); absence ≠ no targets.
- **Names** are lower-case; ~86 are shared by multiple SIDER compounds
  (→ `AMBIGUOUS`).
- **Pathways** are optional, derived, coarse (target-level, no thresholding),
  and only as complete as the drug's target list — a drug with sparse ChEMBL
  targets will have a sparse pathway footprint.
- No brand-name / synonym resolution.
- No chemical-structure fields (deliberately — no consumer yet).

---

## What Level 4 will build

Level 4 begins **Candidate Drug Generation** and downstream: given a Level 2
`DiseaseProfile` and Level 3 `DrugProfile`s, produce a candidate set (e.g. drugs
whose targets/pathways intersect the disease's genes/pathways), then **Feature
Engineering** over the paired profiles — still no ML or scoring at that step.
