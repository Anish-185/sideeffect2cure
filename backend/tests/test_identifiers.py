"""Unit tests for identifier normalization and the internal-id registry.

Fixture values here are synthetic placeholders chosen to exercise parsing rules
(``drugA``, ``C0000001`` ...). They are not biomedical data.
"""

from app.data.constants import EntityType
from app.data.identifiers import (
    IdRegistry,
    normalize_ensembl_gene,
    normalize_name,
    normalize_ontology_id,
    normalize_pubchem_cid,
    normalize_umls_cui,
    normalize_uniprot,
)


def test_normalize_name_collapses_whitespace_and_lowercases():
    assert normalize_name("  Aspirin   Tablet ") == "aspirin tablet"
    assert normalize_name("") is None
    assert normalize_name(None) is None


def test_normalize_pubchem_cid_strips_stitch_prefix_and_flags():
    assert normalize_pubchem_cid("CID100000085") == "85"
    assert normalize_pubchem_cid("CID000010917") == "10917"
    assert normalize_pubchem_cid("2244") == "2244"
    assert normalize_pubchem_cid("not-a-cid") is None


def test_normalize_ontology_id():
    assert normalize_ontology_id("EFO:0000305") == "EFO_0000305"
    assert normalize_ontology_id("mondo_0018177") == "MONDO_0018177"


def test_normalize_ensembl_drops_version_and_checks_prefix():
    assert normalize_ensembl_gene("ENSG00000141510.17") == "ENSG00000141510"
    assert normalize_ensembl_gene("NM_001126112") is None


def test_normalize_umls_and_uniprot():
    assert normalize_umls_cui("C0004096") == "C0004096"
    assert normalize_umls_cui("XYZ") is None
    assert normalize_uniprot("p04637") == "P04637"
    assert normalize_uniprot("bogus") is None


def test_registry_mints_stable_ids_and_records_xrefs():
    reg = IdRegistry()
    a1 = reg.resolve(EntityType.DRUG, "85", primary_source="sider", name="druga")
    a2 = reg.resolve(EntityType.DRUG, "85", primary_source="sider", name="druga")
    b1 = reg.resolve(EntityType.DRUG, "999", primary_source="sider", name="drugb")

    assert a1 == a2 == "DRUG:000001"
    assert b1 == "DRUG:000002"
    assert reg.lookup(EntityType.DRUG, "85") == "DRUG:000001"

    reg.add_xref(a1, EntityType.DRUG, external_id="CHEMBL25", source="chembl")
    mp = reg.mapping_frame()
    row = mp[(mp.internal_id == "DRUG:000001") & (mp.external_source == "chembl")]
    assert row.iloc[0]["external_id"] == "CHEMBL25"
    assert reg.counts()["drug"] == 2


def test_registry_rejects_empty_primary_key():
    reg = IdRegistry()
    try:
        reg.resolve(EntityType.GENE, "", primary_source="opentargets")
    except ValueError:
        return
    raise AssertionError("expected ValueError for empty primary key")
