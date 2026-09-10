"""Unit tests for cross-table data-quality checks.

Synthetic frames only.
"""

import pandas as pd

from app.data.constants import Dataset
from app.data.quality import run_quality_checks
from app.data.report import PipelineReport


def _clean_frames():
    drugs = pd.DataFrame(
        {"drug_id": ["DRUG:1", "DRUG:2"], "drug_name": ["a", "b"], "source": ["sider", "sider"]}
    )
    diseases = pd.DataFrame(
        {"disease_id": ["DIS:1"], "disease_name": ["x"], "source": ["opentargets"]}
    )
    drug_targets = pd.DataFrame(
        {"drug_id": ["DRUG:1"], "target_id": ["TGT:1"], "source": ["chembl"]}
    )
    disease_genes = pd.DataFrame(
        {"disease_id": ["DIS:1"], "gene_id": ["GENE:1"], "source": ["opentargets"]}
    )
    return {
        Dataset.DRUGS: drugs,
        Dataset.DISEASES: diseases,
        Dataset.DRUG_TARGETS: drug_targets,
        Dataset.DISEASE_GENES: disease_genes,
    }


def test_clean_data_passes():
    report = PipelineReport(kind="test")
    run_quality_checks(_clean_frames(), report)
    assert report.ok, [c for c in report.checks if not c.passed]


def test_orphan_relationship_is_hard_failure():
    frames = _clean_frames()
    frames[Dataset.DRUG_TARGETS] = pd.DataFrame(
        {"drug_id": ["DRUG:999"], "target_id": ["TGT:1"], "source": ["chembl"]}
    )
    report = PipelineReport(kind="test")
    run_quality_checks(frames, report)
    assert not report.ok
    assert any("drug_targets.drug_id" in c.name for c in report.hard_failures)


def test_duplicate_primary_key_is_hard_failure():
    frames = _clean_frames()
    frames[Dataset.DRUGS] = pd.concat([frames[Dataset.DRUGS], frames[Dataset.DRUGS]])
    report = PipelineReport(kind="test")
    run_quality_checks(frames, report)
    assert not report.ok
    assert any("unique primary key" in c.name for c in report.hard_failures)
