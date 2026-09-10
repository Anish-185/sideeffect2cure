"""Shared fixtures for Level 2 / Level 3 intelligence tests.

``fixture_repo`` / ``drug_fixture_repo`` are built from small synthetic frames
(obviously not real biomedical data — ``test glioma``, ``GENE:001`` ...) to
exercise resolver / profile logic deterministically.

``real_repo`` / ``real_drug_repo`` use the actual Level 1 processed data and are
skipped if it has not been ingested.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.services.disease.repository import DiseaseRepository
from app.services.drug.repository import DrugRepository


@pytest.fixture
def fixture_frames() -> dict[str, pd.DataFrame]:
    diseases = pd.DataFrame(
        [
            {"disease_id": "DIS:001", "disease_name": "test glioma",
             "ontology_id": "MONDO_9000001", "source": "opentargets"},
            {"disease_id": "DIS:002", "disease_name": "test glioma",  # dup name -> ambiguous
             "ontology_id": "MONDO_9000002", "source": "opentargets"},
            {"disease_id": "DIS:003", "disease_name": "sample carditis",
             "ontology_id": "MONDO_9000003", "source": "opentargets"},
        ]
    )
    disease_genes = pd.DataFrame(
        [
            {"disease_id": "DIS:001", "gene_id": "GENE:001", "gene_name": "AAA",
             "ensembl_id": "ENSG000001", "association_score": 0.9, "source": "opentargets"},
            {"disease_id": "DIS:001", "gene_id": "GENE:002", "gene_name": "BBB",
             "ensembl_id": "ENSG000002", "association_score": 0.4, "source": "opentargets"},
            {"disease_id": "DIS:003", "gene_id": "GENE:003", "gene_name": "CCC",
             "ensembl_id": "ENSG000003", "association_score": 0.7, "source": "opentargets"},
            # malformed: missing gene_id
            {"disease_id": "DIS:001", "gene_id": None, "gene_name": "DDD",
             "ensembl_id": "ENSG000004", "association_score": 0.5, "source": "opentargets"},
            # orphan: unknown disease
            {"disease_id": "DIS:999", "gene_id": "GENE:009", "gene_name": "ZZZ",
             "ensembl_id": "ENSG000009", "association_score": 0.5, "source": "opentargets"},
        ]
    )
    disease_pathways = pd.DataFrame(
        [
            {"disease_id": "DIS:001", "pathway_id": "PATH:001", "pathway_name": "Signalling A",
             "reactome_id": "R-HSA-1", "gene_support_count": 6, "association_score": 0.55,
             "source": "derived:opentargets+reactome"},
            {"disease_id": "DIS:001", "pathway_id": "PATH:002", "pathway_name": "Signalling B",
             "reactome_id": "R-HSA-2", "gene_support_count": 3, "association_score": 0.42,
             "source": "derived:opentargets+reactome"},
        ]
    )
    identifiers = pd.DataFrame(
        [
            {"internal_id": "DIS:001", "entity_type": "disease", "external_id": "MONDO_9000001",
             "external_source": "opentargets", "name": "test glioma", "is_primary": True},
            {"internal_id": "DIS:002", "entity_type": "disease", "external_id": "MONDO_9000002",
             "external_source": "opentargets", "name": "test glioma", "is_primary": True},
            {"internal_id": "DIS:003", "entity_type": "disease", "external_id": "MONDO_9000003",
             "external_source": "opentargets", "name": "sample carditis", "is_primary": True},
        ]
    )
    return {
        "diseases": diseases,
        "disease_genes": disease_genes,
        "disease_pathways": disease_pathways,
        "identifiers": identifiers,
    }


@pytest.fixture
def fixture_repo(fixture_frames) -> DiseaseRepository:
    return DiseaseRepository.from_frames(**fixture_frames)


@pytest.fixture
def real_repo() -> DiseaseRepository:
    from app.data.loaders import DatasetsNotBuilt

    try:
        return DiseaseRepository.from_loaders()
    except DatasetsNotBuilt:
        pytest.skip("Level 1 processed data not present; run scripts/ingest_data.py")


# --- Level 3 (drug) fixtures -----------------------------------------
@pytest.fixture
def drug_fixture_frames() -> dict[str, pd.DataFrame]:
    drugs = pd.DataFrame(
        [
            {"drug_id": "DRUG:001", "drug_name": "test aspirin",
             "canonical_identifier": "CHEMBL900001", "pubchem_cid": "111",
             "chembl_id": "CHEMBL900001", "source": "sider"},
            {"drug_id": "DRUG:002", "drug_name": "test salt",  # dup name -> ambiguous
             "canonical_identifier": "CID:222", "pubchem_cid": "222",
             "chembl_id": None, "source": "sider"},
            {"drug_id": "DRUG:003", "drug_name": "test salt",
             "canonical_identifier": "CHEMBL900003", "pubchem_cid": "333",
             "chembl_id": "CHEMBL900003", "source": "sider"},
        ]
    )
    drug_side_effects = pd.DataFrame(
        [
            {"drug_id": "DRUG:001", "side_effect_id": "SE:001", "side_effect_name": "headache",
             "umls_cui": "C0000001", "source": "sider"},
            {"drug_id": "DRUG:001", "side_effect_id": "SE:002", "side_effect_name": "nausea",
             "umls_cui": "C0000002", "source": "sider"},
            {"drug_id": "DRUG:002", "side_effect_id": "SE:003", "side_effect_name": "rash",
             "umls_cui": "C0000003", "source": "sider"},
            # malformed: missing side_effect_id
            {"drug_id": "DRUG:001", "side_effect_id": None, "side_effect_name": "ghost",
             "umls_cui": "C0000009", "source": "sider"},
            # orphan drug
            {"drug_id": "DRUG:999", "side_effect_id": "SE:009", "side_effect_name": "orphan",
             "umls_cui": "C0000099", "source": "sider"},
        ]
    )
    drug_targets = pd.DataFrame(
        [
            {"drug_id": "DRUG:001", "target_id": "TGT:001", "target_name": "Test Enzyme",
             "target_type": "SINGLE PROTEIN", "uniprot_id": "P0TEST1", "action_type": "INHIBITOR",
             "source": "chembl"},
            {"drug_id": "DRUG:003", "target_id": "TGT:003", "target_name": "Other Enzyme",
             "target_type": "SINGLE PROTEIN", "uniprot_id": None, "action_type": "AGONIST",
             "source": "chembl"},
            # orphan drug
            {"drug_id": "DRUG:999", "target_id": "TGT:009", "target_name": "Orphan",
             "target_type": "SINGLE PROTEIN", "uniprot_id": "P0TEST9", "action_type": "BLOCKER",
             "source": "chembl"},
        ]
    )
    identifiers = pd.DataFrame(
        [
            {"internal_id": "DRUG:001", "entity_type": "drug", "external_id": "CHEMBL900001",
             "external_source": "chembl", "name": None, "is_primary": False},
            {"internal_id": "DRUG:001", "entity_type": "drug", "external_id": "CID:111",
             "external_source": "pubchem", "name": "test aspirin", "is_primary": False},
            {"internal_id": "DRUG:001", "entity_type": "drug", "external_id": "111",
             "external_source": "sider", "name": "test aspirin", "is_primary": True},
            {"internal_id": "DRUG:003", "entity_type": "drug", "external_id": "CHEMBL900003",
             "external_source": "chembl", "name": None, "is_primary": False},
        ]
    )
    return {
        "drugs": drugs,
        "drug_side_effects": drug_side_effects,
        "drug_targets": drug_targets,
        "identifiers": identifiers,
    }


@pytest.fixture
def drug_fixture_repo(drug_fixture_frames) -> DrugRepository:
    return DrugRepository.from_frames(**drug_fixture_frames)


@pytest.fixture
def fake_pathway_index():
    """Stands in for the Reactome UniProt->pathway index (Level 3 + Level 4)."""

    class _Idx:
        def pathways_for(self, uniprot_ids: list[str], *, limit: int | None = None) -> list[dict]:
            _ = limit
            if "P0TEST1" in uniprot_ids:
                return [
                    {"reactome_id": "R-HSA-TEST1", "pathway_name": "Test Pathway One",
                     "supporting_target_count": 1, "supporting_uniprot_ids": ["P0TEST1"]},
                ]
            return []

    return _Idx()


@pytest.fixture
def real_drug_repo() -> DrugRepository:
    from app.data.loaders import DatasetsNotBuilt

    try:
        return DrugRepository.from_loaders()
    except DatasetsNotBuilt:
        pytest.skip("Level 1 processed data not present; run scripts/ingest_data.py")


# --- Level 4 (candidate generation) fixtures -------------------------
@pytest.fixture
def candidate_disease_profile():
    """A DiseaseProfile whose gene ensembl / pathway reactome ids line up with
    the drug fixtures, so both candidate routes can be exercised offline."""
    from app.services.disease import get_disease_profile
    from app.services.disease.repository import DiseaseRepository

    diseases = pd.DataFrame(
        [{"disease_id": "DIS:C1", "disease_name": "candidate test disease",
          "ontology_id": "MONDO_9900001", "source": "opentargets"}]
    )
    genes = pd.DataFrame(
        [
            {"disease_id": "DIS:C1", "gene_id": "GENE:C1", "gene_name": "AAA",
             "ensembl_id": "ENSG000001", "association_score": 0.9, "source": "opentargets"},
            {"disease_id": "DIS:C1", "gene_id": "GENE:C2", "gene_name": "BBB",
             "ensembl_id": "ENSG000002", "association_score": 0.5, "source": "opentargets"},
        ]
    )
    pathways = pd.DataFrame(
        [
            {"disease_id": "DIS:C1", "pathway_id": "PATH:C1", "pathway_name": "Test Pathway One",
             "reactome_id": "R-HSA-TEST1", "gene_support_count": 5, "association_score": 0.6,
             "source": "derived:opentargets+reactome"},
            {"disease_id": "DIS:C1", "pathway_id": "PATH:C2", "pathway_name": "Unmatched pathway",
             "reactome_id": "R-HSA-NOPE", "gene_support_count": 3, "association_score": 0.4,
             "source": "derived:opentargets+reactome"},
        ]
    )
    repo = DiseaseRepository.from_frames(
        diseases=diseases, disease_genes=genes, disease_pathways=pathways
    )
    return get_disease_profile("DIS:C1", repository=repo)


@pytest.fixture
def empty_disease_profile():
    """A valid DiseaseProfile with no genes and no pathways."""
    from app.services.disease import get_disease_profile
    from app.services.disease.repository import DiseaseRepository

    diseases = pd.DataFrame(
        [{"disease_id": "DIS:E1", "disease_name": "empty disease",
          "ontology_id": None, "source": "opentargets"}]
    )
    empty_genes = pd.DataFrame(
        columns=["disease_id", "gene_id", "gene_name", "ensembl_id", "association_score", "source"]
    )
    empty_pw = pd.DataFrame(
        columns=["disease_id", "pathway_id", "pathway_name", "reactome_id",
                 "gene_support_count", "association_score", "source"]
    )
    repo = DiseaseRepository.from_frames(
        diseases=diseases, disease_genes=empty_genes, disease_pathways=empty_pw
    )
    return get_disease_profile("DIS:E1", repository=repo)


@pytest.fixture
def candidate_fixture_index(drug_fixture_repo, drug_fixture_frames, fake_pathway_index):
    from app.services.candidates import CandidateIndex
    from app.services.candidates.bridge import HGNCBridge

    bridge = HGNCBridge(
        ensembl_to_hgnc={"ENSG000001": "HGNC:1", "ENSG000002": "HGNC:2"},
        uniprot_to_hgnc={"P0TEST1": "HGNC:1"},
        hgnc_to_symbol={"HGNC:1": "AAA", "HGNC:2": "BBB"},
    )
    return CandidateIndex.build(
        drug_repo=drug_fixture_repo,
        hgnc_bridge=bridge,
        reactome_index=fake_pathway_index,
        drug_targets=drug_fixture_frames["drug_targets"],
    )


@pytest.fixture
def real_candidate_index():
    from app.data.loaders import DatasetsNotBuilt
    from app.services.candidates import CandidateIndex

    try:
        idx = CandidateIndex.build()
    except DatasetsNotBuilt:
        pytest.skip("Level 1 processed data not present; run scripts/ingest_data.py")
    if not idx.gene_target_available and not idx.pathway_available:
        pytest.skip("neither HGNC nor Reactome enrichment available in this environment")
    return idx


# --- Level 5 (feature engineering) fixtures -------------------------
@pytest.fixture
def feature_inputs(candidate_disease_profile, candidate_fixture_index, drug_fixture_repo):
    """(candidate, disease_profile, drug_profile, index) for fixture drug DRUG:001."""
    from app.services.candidates import generate_candidates
    from app.services.drug import get_drug_profile

    res = generate_candidates(candidate_disease_profile, index=candidate_fixture_index)
    candidate = next(c for c in res.candidates if c.drug_id == "DRUG:001")
    drug_profile = get_drug_profile(
        "DRUG:001", repository=drug_fixture_repo, enrich_pathways=False
    )
    return {
        "candidate": candidate,
        "disease_profile": candidate_disease_profile,
        "drug_profile": drug_profile,
        "index": candidate_fixture_index,
    }
