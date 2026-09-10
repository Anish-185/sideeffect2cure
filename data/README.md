# Data

Local file store for the prototype (CSV / parquet). Downloaded and generated
data is **git-ignored** — only `.gitkeep` files are tracked. Regenerate
everything with `python scripts/ingest_data.py` (see [`../docs/data.md`](../docs/data.md)).

```
raw/         untouched source downloads, one subdir per source
  sider/  chembl/  opentargets/  reactome/
processed/   normalized tables written by the ingestion pipeline
  drugs.{parquet,csv}          diseases.{parquet,csv}
  drug_targets.{parquet,csv}   drug_side_effects.{parquet,csv}
  disease_genes.{parquet,csv}  disease_pathways.{parquet,csv}
  _reports/    ingestion.json / validation.json run reports
mappings/    identifiers.{parquet,csv}  — internal <-> external id crosswalk
features/    ML-ready feature matrices (later levels)
```

Source subdirectories under `raw/` are created by the ingestion script.
