"""Biomedical data foundation (Level 1).

Turns a small, deliberately-scoped set of real public sources (SIDER, ChEMBL,
Open Targets, Reactome) into six normalized processed tables that every later
level joins on internal identifiers:

    drugs, diseases, drug_targets, drug_side_effects, disease_genes,
    disease_pathways

Entry points:
    * ``app.data.ingest.run_ingestion``  - download + normalize + write
    * ``app.data.quality.run_quality_checks`` - cross-table validation
    * ``app.data.loaders`` - read processed datasets (for later levels)

No biomedical values are fabricated anywhere in this package. See docs/data.md.
"""

from app.data.constants import Dataset, EntityType, Source

__all__ = ["Dataset", "EntityType", "Source"]
