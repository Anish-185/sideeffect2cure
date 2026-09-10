#!/usr/bin/env python3
"""Train the Phase 6 prediction model.

    python scripts/train_model.py            # build dataset, CV, fit, save to data/models/
    python scripts/train_model.py --refresh-labels   # re-fetch Open Targets clinical candidates

Reads Levels 2-5 over every ingested disease, labels each candidate with the
Open Targets clinical-candidate target, cross-validates (GroupKFold by disease),
selects the best baseline model and persists it locally. Free / local only.
"""

from __future__ import annotations

import argparse
import json
import sys

import _bootstrap  # noqa: F401

from app.services.ml.dataset import build_training_dataset
from app.services.ml.labels import fetch_known_drugs, reset_label_cache
from app.services.ml.train import cross_validate, select_best, train


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh-labels", action="store_true", help="re-fetch label source")
    args = parser.parse_args(argv)

    if args.refresh_labels:
        from app.services.candidates.repository import default_index
        from app.services.disease.repository import default_repository

        for rec in default_repository()._by_id.values():
            if rec.get("ontology_id"):
                fetch_known_drugs(rec["ontology_id"], force=True)
        reset_label_cache()
        default_index()  # warm

    print("building training dataset (Levels 2-5 over all diseases)...")
    ds = build_training_dataset()
    print(
        f"  rows={ds.n_rows}  positives={ds.n_positive}  "
        f"prevalence={ds.positive_prevalence:.1%}  diseases={ds.n_diseases}"
    )
    if ds.n_positive == 0 or ds.n_positive == ds.n_rows:
        print("  DEGENERATE TARGET — refusing to train a single-class classifier")
        return 1

    print("cross-validating (GroupKFold by disease_id)...")
    cv = cross_validate(ds)
    for name, m in cv.items():
        print(
            f"  {name:20} PR-AUC={m['pr_auc_mean']:.3f}±{m['pr_auc_std']:.3f}  "
            f"ROC-AUC={m['roc_auc_mean']:.3f}±{m['roc_auc_std']:.3f}  "
            f"P={m['precision_mean']:.3f} R={m['recall_mean']:.3f} F1={m['f1_mean']:.3f}"
        )
    print(f"  no-skill PR-AUC (prevalence) = {ds.positive_prevalence:.3f}")
    print(f"selected: {select_best(cv)}")

    model = train(ds)
    path = model.save()
    print(f"\nsaved {model.name} v{model.metadata.model_version} -> {path}")
    print("top global features:")
    for name, imp in model.global_importance()[:10]:
        print(f"  {name:48} {imp:.4f}")
    print("\nmetadata:")
    print(json.dumps(model.metadata.model_dump()["validation"], indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
