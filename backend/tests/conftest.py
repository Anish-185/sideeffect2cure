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
    """Stands in for the Reactome UniProt->pathway index."""

    class _Idx:
        def pathways_for(self, uniprot_ids: list[str]) -> list[dict]:
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
