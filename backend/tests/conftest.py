"""Shared fixtures for Level 2 disease-intelligence tests.

``fixture_repo`` is built from small synthetic frames (obviously not real
biomedical data — ``test glioma``, ``GENE:001`` ...) to exercise resolver /
profile logic deterministically.

``real_repo`` uses the actual Level 1 processed data and is skipped if it has
not been ingested.
"""

from __future__ import annotations

import pandas as pd
import pytest

from app.services.disease.repository import DiseaseRepository


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
