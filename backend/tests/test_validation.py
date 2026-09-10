"""Unit tests for frame-level ingestion validation.

All rows here are synthetic test doubles, not biomedical data.
"""

import pandas as pd

from app.data.constants import Dataset
from app.data.report import StageReport
from app.data.validation import coerce_and_validate, expected_columns


def test_drops_rows_missing_required_fields():
    df = pd.DataFrame(
        [
            {"drug_id": "DRUG:1", "drug_name": "a", "source": "sider"},
            {"drug_id": None, "drug_name": "b", "source": "sider"},
            {"drug_id": "DRUG:3", "drug_name": "", "source": "sider"},
        ]
    )
    stage = StageReport(name="t")
    out = coerce_and_validate(Dataset.DRUGS, df, stage)
    assert list(out["drug_id"]) == ["DRUG:1"]
    assert stage.rejections["missing_required_field"].count == 2
    assert set(out.columns) == set(expected_columns(Dataset.DRUGS))


def test_deduplicates_primary_key():
    df = pd.DataFrame(
        [
            {"disease_id": "DIS:1", "gene_id": "GENE:1", "source": "opentargets"},
            {"disease_id": "DIS:1", "gene_id": "GENE:1", "source": "opentargets"},
            {"disease_id": "DIS:1", "gene_id": "GENE:2", "source": "opentargets"},
        ]
    )
    stage = StageReport(name="t")
    out = coerce_and_validate(Dataset.DISEASE_GENES, df, stage)
    assert len(out) == 2
    assert stage.rejections["duplicate_primary_key"].count == 1


def test_rejects_out_of_range_score():
    df = pd.DataFrame(
        [
            {"disease_id": "DIS:1", "gene_id": "GENE:1", "association_score": 0.5,
             "source": "opentargets"},
            {"disease_id": "DIS:1", "gene_id": "GENE:2", "association_score": 5.0,
             "source": "opentargets"},
        ]
    )
    stage = StageReport(name="t")
    out = coerce_and_validate(Dataset.DISEASE_GENES, df, stage)
    assert list(out["gene_id"]) == ["GENE:1"]
    assert stage.rejections["schema_violation"].count == 1


def test_adds_missing_optional_columns():
    df = pd.DataFrame([{"drug_id": "DRUG:1", "drug_name": "a", "source": "sider"}])
    stage = StageReport(name="t")
    out = coerce_and_validate(Dataset.DRUGS, df, stage)
    assert "chembl_id" in out.columns
    assert out.iloc[0]["chembl_id"] is None or pd.isna(out.iloc[0]["chembl_id"])
