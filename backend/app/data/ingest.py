"""Reproducible ingestion / normalization pipeline (Level 1).

    raw data
      -> validation (schema / required fields)
      -> cleaning (whitespace, empty -> null)
      -> identifier normalization (external ids -> canonical form)
      -> deduplication (entities + relationships)
      -> structured processed datasets (parquet + csv)
      -> data-quality checks (app.data.quality)

The orchestrator is resilient: if a source is unavailable, the datasets that
depend on it are skipped (and reported) while the rest still build.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from app.core.config import get_settings
from app.data import identifiers as idn
from app.data.constants import (
    DATA_SNAPSHOT_NOTE,
    DISEASE_PATHWAY_MIN_GENES,
    Dataset,
    EntityType,
    Source,
)
from app.data.paths import DataPaths
from app.data.quality import run_quality_checks
from app.data.report import PipelineReport, StageReport
from app.data.sources import (
    ChemblSource,
    OpenTargetsSource,
    ReactomeSource,
    SiderSource,
)
from app.data.sources.base import BaseSource, SourceUnavailable
from app.data.validation import coerce_and_validate
from app.data.writers import write_dataset, write_mapping

SOURCE_CLASSES: dict[Source, type[BaseSource]] = {
    Source.SIDER: SiderSource,
    Source.CHEMBL: ChemblSource,
    Source.OPENTARGETS: OpenTargetsSource,
    Source.REACTOME: ReactomeSource,
}


@dataclass
class IngestContext:
    paths: DataPaths
    report: PipelineReport
    registry: idn.IdRegistry = field(default_factory=idn.IdRegistry)
    sources: dict[Source, BaseSource] = field(default_factory=dict)
    ready: set[Source] = field(default_factory=set)
    frames: dict[Dataset, pd.DataFrame] = field(default_factory=dict)
    # normalized-key -> internal id, for cross-dataset joins
    drug_by_cid: dict[str, str] = field(default_factory=dict)
    drug_by_chembl: dict[str, str] = field(default_factory=dict)
    disease_by_ontology: dict[str, str] = field(default_factory=dict)
    gene_by_ensembl: dict[str, str] = field(default_factory=dict)
    target_by_chembl: dict[str, str] = field(default_factory=dict)
    pathway_by_reactome: dict[str, str] = field(default_factory=dict)


# --- download / availability -------------------------------------------
def prepare_sources(
    ctx: IngestContext, requested: list[Source], *, offline: bool, force: bool
) -> None:
    for src in requested:
        source = SOURCE_CLASSES[src](ctx.paths)
        ctx.sources[src] = source
        stage = ctx.report.add_stage(StageReport(name=f"download:{src.value}"))
        if not offline:
            try:
                source.download(force=force)
            except SourceUnavailable as exc:
                stage.available = False
                stage.note = str(exc)
        if source.available():
            ctx.ready.add(src)
            stage.note = stage.note or (source.license_note)
        else:
            stage.available = False
            stage.note = stage.note or "raw inputs not present"


def _finalize(ctx: IngestContext, dataset: Dataset, df: pd.DataFrame, stage: StageReport):
    df = coerce_and_validate(dataset, df, stage)
    ctx.frames[dataset] = df
    ctx.report.dataset_counts[dataset.value] = len(df)
    return df


# --- drugs ------------------------------------------------------------
def build_drugs(ctx: IngestContext) -> None:
    if Source.SIDER not in ctx.ready:
        ctx.report.add_stage(
            StageReport(name="build:drugs", available=False, note="requires SIDER")
        )
        return
    stage = ctx.report.add_stage(StageReport(name="build:drugs"))
    sider: SiderSource = ctx.sources[Source.SIDER]  # type: ignore[assignment]
    raw = sider.extract_drugs()

    # chembl <-> pubchem map (optional)
    cid_to_chembl: dict[str, str] = {}
    if Source.CHEMBL in ctx.ready:
        chembl: ChemblSource = ctx.sources[Source.CHEMBL]  # type: ignore[assignment]
        m = chembl.extract_chembl_pubchem()
        m["pubchem_cid"] = m["pubchem_cid"].map(idn.normalize_pubchem_cid)
        m["chembl_id"] = m["chembl_id"].map(idn.normalize_chembl_id)
        m = m.dropna().drop_duplicates("pubchem_cid")
        cid_to_chembl = dict(zip(m["pubchem_cid"], m["chembl_id"], strict=True))

    rows = []
    for _, r in raw.iterrows():
        cid = idn.normalize_pubchem_cid(r["stitch_id"])
        name = idn.normalize_name(r["drug_name"])
        if cid is None:
            stage.reject("unmappable_pubchem_cid", r["stitch_id"])
            continue
        if name is None:
            stage.reject("missing_name", r["stitch_id"])
            continue
        internal = ctx.registry.resolve(
            EntityType.DRUG, cid, primary_source=Source.SIDER.value, name=name
        )
        ctx.registry.add_xref(
            internal, EntityType.DRUG, external_id=f"CID:{cid}", source="pubchem", name=name
        )
        chembl_id = cid_to_chembl.get(cid)
        if chembl_id:
            ctx.registry.add_xref(
                internal, EntityType.DRUG, external_id=chembl_id, source=Source.CHEMBL.value
            )
            ctx.drug_by_chembl.setdefault(chembl_id, internal)
        ctx.drug_by_cid[cid] = internal
        rows.append(
            {
                "drug_id": internal,
                "drug_name": name,
                "canonical_identifier": chembl_id or f"CID:{cid}",
                "pubchem_cid": cid,
                "chembl_id": chembl_id,
                "source": Source.SIDER.value,
            }
        )
    _finalize(ctx, Dataset.DRUGS, pd.DataFrame(rows), stage)


# --- drug -> side effect --------------------------------------------
def build_drug_side_effects(ctx: IngestContext) -> None:
    if Source.SIDER not in ctx.ready or Dataset.DRUGS not in ctx.frames:
        ctx.report.add_stage(
            StageReport(name="build:drug_side_effects", available=False, note="requires SIDER+drugs")
        )
        return
    stage = ctx.report.add_stage(StageReport(name="build:drug_side_effects"))
    sider: SiderSource = ctx.sources[Source.SIDER]  # type: ignore[assignment]
    raw = sider.extract_side_effects()

    rows = []
    for _, r in raw.iterrows():
        cid = idn.normalize_pubchem_cid(r["stitch_id"])
        cui = idn.normalize_umls_cui(r["umls_cui"])
        se_name = idn.normalize_name(r["side_effect_name"])
        if cid is None or cid not in ctx.drug_by_cid:
            stage.reject("drug_not_in_drugs", r["stitch_id"])
            continue
        if cui is None:
            stage.reject("unmappable_umls_cui", r.get("umls_cui"))
            continue
        if se_name is None:
            stage.reject("missing_side_effect_name", cui)
            continue
        se_internal = ctx.registry.resolve(
            EntityType.SIDE_EFFECT, cui, primary_source=Source.SIDER.value, name=se_name
        )
        rows.append(
            {
                "drug_id": ctx.drug_by_cid[cid],
                "side_effect_id": se_internal,
                "side_effect_name": se_name,
                "umls_cui": cui,
                "source": Source.SIDER.value,
            }
        )
    _finalize(ctx, Dataset.DRUG_SIDE_EFFECTS, pd.DataFrame(rows), stage)


# --- diseases + disease -> gene ------------------------------------
def build_diseases_and_genes(ctx: IngestContext) -> None:
    if Source.OPENTARGETS not in ctx.ready:
        for name in ("build:diseases", "build:disease_genes"):
            ctx.report.add_stage(
                StageReport(name=name, available=False, note="requires Open Targets")
            )
        return
    ot: OpenTargetsSource = ctx.sources[Source.OPENTARGETS]  # type: ignore[assignment]

    # diseases
    stage_d = ctx.report.add_stage(StageReport(name="build:diseases"))
    dis_raw = ot.extract_diseases()
    rows = []
    for _, r in dis_raw.iterrows():
        oid = idn.normalize_ontology_id(r["ontology_id"])
        name = idn.normalize_name(r["disease_name"])
        if oid is None or name is None:
            stage_d.reject("missing_id_or_name", r.to_dict())
            continue
        internal = ctx.registry.resolve(
            EntityType.DISEASE, oid, primary_source=Source.OPENTARGETS.value, name=name
        )
        ctx.disease_by_ontology[oid] = internal
        rows.append(
            {
                "disease_id": internal,
                "disease_name": name,
                "ontology_id": oid,
                "source": Source.OPENTARGETS.value,
            }
        )
    if ot.unresolved:
        stage_d.note = f"seed ids not resolvable in Open Targets: {', '.join(ot.unresolved)}"
        for oid in ot.unresolved:
            stage_d.reject("seed_id_unresolved", oid)
    _finalize(ctx, Dataset.DISEASES, pd.DataFrame(rows), stage_d)

    # disease -> gene
    stage_g = ctx.report.add_stage(StageReport(name="build:disease_genes"))
    dg_raw = ot.extract_disease_genes()
    rows = []
    for _, r in dg_raw.iterrows():
        oid = idn.normalize_ontology_id(r["ontology_id"])
        ens = idn.normalize_ensembl_gene(r["ensembl_id"])
        if oid is None or oid not in ctx.disease_by_ontology:
            stage_g.reject("disease_not_in_diseases", r.get("ontology_id"))
            continue
        if ens is None:
            stage_g.reject("unmappable_ensembl_id", r.get("ensembl_id"))
            continue
        sym = idn.normalize_name(r.get("gene_symbol"))
        gene_internal = ctx.registry.resolve(
            EntityType.GENE, ens, primary_source=Source.OPENTARGETS.value, name=sym
        )
        ctx.gene_by_ensembl.setdefault(ens, gene_internal)
        score = r.get("association_score")
        rows.append(
            {
                "disease_id": ctx.disease_by_ontology[oid],
                "gene_id": gene_internal,
                "gene_name": (r.get("gene_symbol") or None),
                "ensembl_id": ens,
                "association_score": float(score) if pd.notna(score) else None,
                "source": Source.OPENTARGETS.value,
            }
        )
    df = pd.DataFrame(rows)
    if not df.empty:
        df = (
            df.sort_values("association_score", ascending=False, na_position="last")
            .drop_duplicates(["disease_id", "gene_id"], keep="first")
        )
    _finalize(ctx, Dataset.DISEASE_GENES, df, stage_g)


# --- drug -> target ------------------------------------------------
def build_drug_targets(ctx: IngestContext) -> None:
    if Source.CHEMBL not in ctx.ready or Dataset.DRUGS not in ctx.frames:
        ctx.report.add_stage(
            StageReport(name="build:drug_targets", available=False, note="requires ChEMBL+drugs")
        )
        return
    stage = ctx.report.add_stage(StageReport(name="build:drug_targets"))
    chembl: ChemblSource = ctx.sources[Source.CHEMBL]  # type: ignore[assignment]

    targets = chembl.extract_targets()
    target_meta: dict[str, dict] = {}
    for _, t in targets.iterrows():
        tcid = idn.normalize_chembl_id(t["target_chembl_id"])
        if tcid is None:
            continue
        tname = t.get("target_name") or None
        internal = ctx.registry.resolve(
            EntityType.TARGET, tcid, primary_source=Source.CHEMBL.value, name=tname
        )
        uni = idn.normalize_uniprot(t.get("uniprot_id"))
        if uni:
            ctx.registry.add_xref(
                internal, EntityType.TARGET, external_id=uni, source="uniprot"
            )
        ctx.target_by_chembl[tcid] = internal
        target_meta[tcid] = {
            "target_id": internal,
            "target_name": tname,
            "target_type": t.get("target_type") or None,
            "uniprot_id": uni,
        }

    mech = chembl.extract_mechanisms()
    rows = []
    for _, m in mech.iterrows():
        mol = idn.normalize_chembl_id(m["chembl_id"])
        tcid = idn.normalize_chembl_id(m["target_chembl_id"])
        drug_internal = ctx.drug_by_chembl.get(mol) if mol else None
        if drug_internal is None:
            stage.reject("drug_not_in_drugs", m.get("chembl_id"))
            continue
        meta = target_meta.get(tcid)
        if meta is None:
            stage.reject("target_details_unavailable", m.get("target_chembl_id"))
            continue
        rows.append(
            {
                "drug_id": drug_internal,
                "target_id": meta["target_id"],
                "target_name": meta["target_name"],
                "target_type": meta["target_type"],
                "uniprot_id": meta["uniprot_id"],
                "action_type": m.get("action_type") or None,
                "source": Source.CHEMBL.value,
            }
        )
    _finalize(ctx, Dataset.DRUG_TARGETS, pd.DataFrame(rows), stage)


# --- disease -> pathway (DERIVED) --------------------------------
def build_disease_pathways(ctx: IngestContext) -> None:
    have = Source.REACTOME in ctx.ready and Dataset.DISEASE_GENES in ctx.frames
    if not have:
        ctx.report.add_stage(
            StageReport(
                name="build:disease_pathways",
                available=False,
                note="requires Reactome + disease_genes",
            )
        )
        return
    stage = ctx.report.add_stage(StageReport(name="build:disease_pathways"))
    stage.note = "DERIVED: Open Targets disease genes x Reactome gene->pathway"
    reactome: ReactomeSource = ctx.sources[Source.REACTOME]  # type: ignore[assignment]

    pw = reactome.extract_pathways()
    pw["reactome_id"] = pw["reactome_id"].map(idn.normalize_reactome_id)
    pw_name = dict(zip(pw["reactome_id"], pw["pathway_name"], strict=True))

    gp = reactome.extract_gene_pathways()
    gp["ensembl_id"] = gp["ensembl_id"].map(idn.normalize_ensembl_gene)
    gp["reactome_id"] = gp["reactome_id"].map(idn.normalize_reactome_id)
    gp = gp.dropna(subset=["ensembl_id", "reactome_id"]).drop_duplicates(
        ["ensembl_id", "reactome_id"]
    )

    dg = ctx.frames[Dataset.DISEASE_GENES][
        ["disease_id", "ensembl_id", "association_score"]
    ].copy()
    merged = dg.merge(gp[["ensembl_id", "reactome_id"]], on="ensembl_id", how="inner")
    if merged.empty:
        _finalize(ctx, Dataset.DISEASE_PATHWAYS, pd.DataFrame(), stage)
        return

    agg = (
        merged.groupby(["disease_id", "reactome_id"])
        .agg(
            gene_support_count=("ensembl_id", "nunique"),
            association_score=("association_score", "mean"),
        )
        .reset_index()
    )
    kept = agg[agg["gene_support_count"] >= DISEASE_PATHWAY_MIN_GENES].copy()
    dropped = len(agg) - len(kept)
    stage.note += (
        f" | {len(agg)} candidate (disease,pathway) pairs; "
        f"{dropped} dropped for < {DISEASE_PATHWAY_MIN_GENES} supporting genes"
    )
    if dropped:
        below = agg[agg["gene_support_count"] < DISEASE_PATHWAY_MIN_GENES]
        for _, r in below.head(10).iterrows():
            stage.reject(
                "below_min_gene_support",
                {k: r[k] for k in ("disease_id", "reactome_id")},
            )
        stage.rejections["below_min_gene_support"].count = dropped

    rows = []
    for _, r in kept.iterrows():
        rid = r["reactome_id"]
        name = pw_name.get(rid) or "unknown pathway"
        internal = ctx.registry.resolve(
            EntityType.PATHWAY, rid, primary_source=Source.REACTOME.value, name=name
        )
        ctx.pathway_by_reactome[rid] = internal
        rows.append(
            {
                "disease_id": r["disease_id"],
                "pathway_id": internal,
                "pathway_name": name,
                "reactome_id": rid,
                "gene_support_count": int(r["gene_support_count"]),
                "association_score": (
                    round(float(r["association_score"]), 6)
                    if pd.notna(r["association_score"])
                    else None
                ),
                "source": "derived:opentargets+reactome",
            }
        )
    _finalize(ctx, Dataset.DISEASE_PATHWAYS, pd.DataFrame(rows), stage)


# --- orchestrator --------------------------------------------------
def run_ingestion(
    *,
    sources: list[Source] | None = None,
    offline: bool = False,
    force: bool = False,
    paths: DataPaths | None = None,
) -> PipelineReport:
    paths = paths or DataPaths.from_settings(get_settings())
    paths.ensure_dirs()
    report = PipelineReport(kind="ingestion")
    report.stages.append(StageReport(name="snapshot", note=DATA_SNAPSHOT_NOTE))
    ctx = IngestContext(paths=paths, report=report)

    requested = sources or list(SOURCE_CLASSES)
    prepare_sources(ctx, requested, offline=offline, force=force)

    build_drugs(ctx)
    build_drug_side_effects(ctx)
    build_diseases_and_genes(ctx)
    build_drug_targets(ctx)
    build_disease_pathways(ctx)

    for dataset, df in ctx.frames.items():
        write_dataset(paths, dataset, df)
    write_mapping(paths, ctx.registry.mapping_frame())

    report.entity_counts = ctx.registry.counts()
    run_quality_checks(ctx.frames, report)
    report.write(paths.report_json("ingestion"))
    return report
