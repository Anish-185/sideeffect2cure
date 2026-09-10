"""Constants for the biomedical data foundation (Level 1).

Everything that later levels need in order to *locate* or *interpret* the
processed datasets lives here: source definitions, download URLs, the internal
identifier scheme, and the canonical list of processed tables.

No biomedical values are hard-coded in this module. The disease seed list is a
list of ontology *identifiers to include* (an input parameter); the disease
names and every association are fetched from the real sources at ingest time.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path

RESOURCES_DIR = Path(__file__).resolve().parent / "resources"

# Reference date of the third-party snapshots documented in docs/data.md.
DATA_SNAPSHOT_NOTE = (
    "SIDER 4.1 (2015-10) static release; ChEMBL current REST release; "
    "Open Targets Platform current GraphQL API; Reactome current release."
)


class EntityType(str, Enum):
    """Primary entity namespaces that get an internal identifier."""

    DRUG = "drug"
    DISEASE = "disease"
    GENE = "gene"
    TARGET = "target"
    PATHWAY = "pathway"
    SIDE_EFFECT = "side_effect"


# Prefix used when minting internal ids, e.g. ``DRUG:000123``.
ID_PREFIXES: dict[EntityType, str] = {
    EntityType.DRUG: "DRUG",
    EntityType.DISEASE: "DIS",
    EntityType.GENE: "GENE",
    EntityType.TARGET: "TGT",
    EntityType.PATHWAY: "PATH",
    EntityType.SIDE_EFFECT: "SE",
}

INTERNAL_ID_WIDTH = 6


class Source(str, Enum):
    """Third-party data sources used by Level 1."""

    SIDER = "sider"
    CHEMBL = "chembl"
    OPENTARGETS = "opentargets"
    REACTOME = "reactome"
    PUBCHEM = "pubchem"
    DERIVED = "derived"


# --- Download endpoints -------------------------------------------------------
# SIDER 4.1 flat files (drug names + MedDRA side effects).
SIDER_BASE_URL = "https://sideeffects.embl.de/media/download"
SIDER_FILES: dict[str, str] = {
    "drug_names.tsv": f"{SIDER_BASE_URL}/drug_names.tsv",
    "drug_atc.tsv": f"{SIDER_BASE_URL}/drug_atc.tsv",
    "meddra_all_se.tsv.gz": f"{SIDER_BASE_URL}/meddra_all_se.tsv.gz",
    "meddra_all_indications.tsv.gz": f"{SIDER_BASE_URL}/meddra_all_indications.tsv.gz",
}

# ChEMBL REST API (paginated JSON).
CHEMBL_API_BASE = "https://www.ebi.ac.uk/chembl/api/data"

# PubChem PUG-REST: used to map SIDER drugs (PubChem CID) -> ChEMBL id via the
# compound's registered synonyms. Batched, ~150 CIDs per request.
PUBCHEM_PUG_REST = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
PUBCHEM_CID_BATCH = 150

# Open Targets Platform GraphQL API.
OPENTARGETS_GRAPHQL_URL = "https://api.platform.opentargets.org/api/v4/graphql"

# Reactome current-release flat files.
REACTOME_BASE_URL = "https://reactome.org/download/current"
REACTOME_FILES: dict[str, str] = {
    "ReactomePathways.txt": f"{REACTOME_BASE_URL}/ReactomePathways.txt",
    "Ensembl2Reactome.txt": f"{REACTOME_BASE_URL}/Ensembl2Reactome.txt",
}

REACTOME_HUMAN_SPECIES = "Homo sapiens"

# Species tag Open Targets / Ensembl use for human gene ids.
ENSEMBL_GENE_PREFIX = "ENSG"

# File that lists which disease ontology ids to ingest (one per line, '#'
# comments allowed). Tracked in git; edit it to widen/narrow disease scope.
DISEASE_SEED_FILE = RESOURCES_DIR / "disease_seed.tsv"

# Cap on associated targets pulled per disease from Open Targets (keeps the
# prototype dataset manageable; the strongest associations come first).
OPENTARGETS_TARGETS_PER_DISEASE = 200

# disease_pathways is DERIVED (Open Targets disease genes x Reactome gene->pathway).
# Only keep a (disease, pathway) pair supported by at least this many disease
# genes -- keeps the table to biologically meaningful enrichment and manageable
# in size. Downstream levels can filter further using ``gene_support_count``.
DISEASE_PATHWAY_MIN_GENES = 3


# --- Processed dataset catalogue --------------------------------------------
class Dataset(str, Enum):
    """Canonical processed tables written to ``data/processed``."""

    DRUGS = "drugs"
    DISEASES = "diseases"
    DRUG_TARGETS = "drug_targets"
    DRUG_SIDE_EFFECTS = "drug_side_effects"
    DISEASE_GENES = "disease_genes"
    DISEASE_PATHWAYS = "disease_pathways"


# Relationship table -> (column, entity table it must reference).
REFERENTIAL_INTEGRITY: dict[Dataset, tuple[tuple[str, Dataset], ...]] = {
    Dataset.DRUG_TARGETS: (("drug_id", Dataset.DRUGS),),
    Dataset.DRUG_SIDE_EFFECTS: (("drug_id", Dataset.DRUGS),),
    Dataset.DISEASE_GENES: (("disease_id", Dataset.DISEASES),),
    Dataset.DISEASE_PATHWAYS: (("disease_id", Dataset.DISEASES),),
}

# Primary-key column(s) for each dataset (used by dedup + quality checks).
PRIMARY_KEYS: dict[Dataset, tuple[str, ...]] = {
    Dataset.DRUGS: ("drug_id",),
    Dataset.DISEASES: ("disease_id",),
    Dataset.DRUG_TARGETS: ("drug_id", "target_id"),
    Dataset.DRUG_SIDE_EFFECTS: ("drug_id", "side_effect_id"),
    Dataset.DISEASE_GENES: ("disease_id", "gene_id"),
    Dataset.DISEASE_PATHWAYS: ("disease_id", "pathway_id"),
}

MAPPING_TABLE_NAME = "identifiers"
