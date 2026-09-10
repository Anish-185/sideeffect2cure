# Data

Local file store for the prototype (CSV / parquet). No biomedical datasets are
downloaded or committed at Level 0.

- `raw/` — untouched source extracts as downloaded.
- `processed/` — cleaned, normalized tables derived from `raw/`.
- `features/` — ML-ready feature matrices.

Contents of these folders are git-ignored; only `.gitkeep` files are tracked.
Dataset acquisition scripts will live in `../scripts/`.
