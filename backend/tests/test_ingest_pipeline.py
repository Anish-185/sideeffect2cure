"""End-to-end test of the ingestion pipeline with fake in-memory sources.

The fakes return small synthetic frames shaped like each real source's output.
These are obviously-synthetic test doubles (``testdrug``, ``ENSGTEST*``); no
real biomedical data is asserted. The point is to exercise the *pipeline*:
normalization, id minting, dedup, the derived disease_pathways table, and the
cross-table quality checks.
"""

import pandas as pd
import pytest

from app.data import ingest
from app.data.constants import Dataset, Source
from app.data.ingest import run_ingestion
from app.data.paths import DataPaths


class _Fake:
    license_note = "test"

    def __init__(self, paths):
        self.paths = paths

    def download(self, *, force=False):
        return None

    def available(self):
        return True


class FakeSider(_Fake):
    source = Source.SIDER

    def extract_drugs(self):
        return pd.DataFrame(
            {
                "stitch_id": ["CID100000001", "CID100000002", "CID100000002", "bad"],
                "drug_name": ["Testdrug A", "Testdrug B", "Testdrug B dup", "Nameless"],
            }
        )

    def extract_side_effects(self):
        return pd.DataFrame(
            {
                "stitch_id": ["CID100000001", "CID100000001", "CID100000002", "CID100099999"],
                "umls_cui": ["C0000111", "C0000111", "C0000222", "C0000333"],
                "side_effect_name": ["Headache", "Headache", "Nausea", "Orphan SE"],
            }
        )


class FakeChembl(_Fake):
    source = Source.CHEMBL

    def extract_chembl_pubchem(self):
        return pd.DataFrame(
            {"chembl_id": ["CHEMBL1", "CHEMBL2"], "pubchem_cid": ["1", "2"]}
        )

    def extract_mechanisms(self):
        return pd.DataFrame(
            {
                "chembl_id": ["CHEMBL1", "CHEMBL1", "CHEMBL2", "CHEMBL999"],
                "target_chembl_id": ["CHEMBL_T1", "CHEMBL_T1", "CHEMBL_T2", "CHEMBL_T1"],
                "action_type": ["INHIBITOR", "INHIBITOR", "AGONIST", "INHIBITOR"],
                "mechanism_of_action": ["x", "x", "y", "z"],
            }
        )

    def extract_targets(self):
        return pd.DataFrame(
            {
                "target_chembl_id": ["CHEMBL_T1", "CHEMBL_T2"],
                "target_name": ["Target One", "Target Two"],
                "target_type": ["SINGLE PROTEIN", "SINGLE PROTEIN"],
                "uniprot_id": ["P04637", None],
                "gene_symbol": ["TP53", "EGFR"],
            }
        )


class FakeOpenTargets(_Fake):
    source = Source.OPENTARGETS

    def __init__(self, paths):
        super().__init__(paths)
        self.unresolved = ["MONDO_9999999"]

    def extract_diseases(self):
        return pd.DataFrame(
            {
                "ontology_id": ["MONDO_0000001", "MONDO_0000002"],
                "disease_name": ["Test Disease One", "Test Disease Two"],
            }
        )

    def extract_disease_genes(self):
        return pd.DataFrame(
            {
                "ontology_id": ["MONDO_0000001"] * 4 + ["MONDO_0000002", "BAD_ID"],
                "ensembl_id": [
                    "ENSGTEST01",
                    "ENSGTEST02",
                    "ENSGTEST03",
                    "ENSGTEST03",  # dup pair -> deduped
                    "ENSGTEST01",
                    "ENSGTEST09",
                ],
                "gene_symbol": ["G1", "G2", "G3", "G3", "G1", "GX"],
                "gene_full_name": ["gene one", "g2", "g3", "g3", "gene one", "gx"],
                "association_score": [0.9, 0.8, 0.7, 0.4, 0.5, 0.5],
            }
        )


class FakeReactome(_Fake):
    source = Source.REACTOME

    def extract_pathways(self):
        return pd.DataFrame(
            {
                "reactome_id": ["R-HSA-1", "R-HSA-2"],
                "pathway_name": ["Pathway One", "Pathway Two"],
            }
        )

    def extract_gene_pathways(self):
        # 3 genes of MONDO_0000001 all map to R-HSA-1  -> passes min_genes=3
        return pd.DataFrame(
            {
                "ensembl_id": ["ENSGTEST01", "ENSGTEST02", "ENSGTEST03", "ENSGTEST01"],
                "reactome_id": ["R-HSA-1", "R-HSA-1", "R-HSA-1", "R-HSA-2"],
                "pathway_name": ["Pathway One"] * 3 + ["Pathway Two"],
                "evidence_code": ["IEA"] * 4,
            }
        )


@pytest.fixture
def fake_sources(monkeypatch):
    monkeypatch.setattr(
        ingest,
        "SOURCE_CLASSES",
        {
            Source.SIDER: FakeSider,
            Source.CHEMBL: FakeChembl,
            Source.OPENTARGETS: FakeOpenTargets,
            Source.REACTOME: FakeReactome,
        },
    )


def test_pipeline_builds_all_datasets(tmp_path, fake_sources):
    paths = DataPaths(
        root=tmp_path,
        raw=tmp_path / "raw",
        processed=tmp_path / "processed",
        mappings=tmp_path / "mappings",
        reports=tmp_path / "processed" / "_reports",
    )
    report = run_ingestion(offline=True, paths=paths)

    assert report.ok, report.render()

    drugs = pd.read_parquet(paths.processed_parquet(Dataset.DRUGS))
    diseases = pd.read_parquet(paths.processed_parquet(Dataset.DISEASES))
    dse = pd.read_parquet(paths.processed_parquet(Dataset.DRUG_SIDE_EFFECTS))
    dt = pd.read_parquet(paths.processed_parquet(Dataset.DRUG_TARGETS))
    dg = pd.read_parquet(paths.processed_parquet(Dataset.DISEASE_GENES))
    dp = pd.read_parquet(paths.processed_parquet(Dataset.DISEASE_PATHWAYS))

    # drugs: 2 unique (dup collapsed, nameless + bad-cid dropped)
    assert len(drugs) == 2
    assert set(drugs["chembl_id"]) == {"CHEMBL1", "CHEMBL2"}

    # side effects: orphan drug row (CID100099999) dropped, dup pair collapsed
    assert len(dse) == 2
    assert set(dse["umls_cui"]) == {"C0000111", "C0000222"}

    # drug_targets: CHEMBL999 (no drug) dropped, dup collapsed -> 2 rows
    assert len(dt) == 2
    assert set(dt["action_type"]) == {"INHIBITOR", "AGONIST"}

    # disease_genes: BAD_ID disease dropped, dup pair deduped keeping max score
    assert len(dg) == 4
    row = dg[(dg.ensembl_id == "ENSGTEST03")].iloc[0]
    assert row["association_score"] == 0.7

    # derived disease_pathways: only R-HSA-1 for MONDO_0000001 (3 genes)
    assert len(dp) == 1
    assert dp.iloc[0]["gene_support_count"] == 3
    assert dp.iloc[0]["source"] == "derived:opentargets+reactome"

    # mapping table has primary + secondary xrefs
    mp = pd.read_parquet(paths.mapping_parquet())
    assert (mp["is_primary"]).any()
    assert set(mp["entity_type"]) >= {"drug", "disease", "gene", "target", "pathway", "side_effect"}

    assert len(diseases) == 2


def test_pipeline_resilient_to_missing_source(tmp_path, monkeypatch):
    # only SIDER available -> drugs + side effects build, the rest are skipped
    monkeypatch.setattr(ingest, "SOURCE_CLASSES", {Source.SIDER: FakeSider})
    paths = DataPaths(
        root=tmp_path,
        raw=tmp_path / "raw",
        processed=tmp_path / "processed",
        mappings=tmp_path / "mappings",
        reports=tmp_path / "processed" / "_reports",
    )
    report = run_ingestion(sources=[Source.SIDER], offline=True, paths=paths)
    assert report.ok, report.render()
    assert paths.processed_parquet(Dataset.DRUGS).exists()
    assert not paths.processed_parquet(Dataset.DISEASES).exists()
