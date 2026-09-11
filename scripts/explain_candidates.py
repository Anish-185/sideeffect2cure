#!/usr/bin/env python3
"""Phase 9 demo: run the full pipeline for one disease and explain its top-N
ranked candidates.

    python scripts/explain_candidates.py                     # GBM, top 3
    python scripts/explain_candidates.py "Alzheimer disease" --top-n 5

Runs candidate generation -> features -> ML -> evidence fusion -> ranking
(Levels 4-8, unchanged), then Phase 9: for each of the top-N ranked
candidates, builds an ``ExplanationContext`` and asks the configured
explanation provider to narrate it.

Uses ``deepseek-ai/DeepSeek-V4-Flash-0731`` via Featherless when
``FEATHERLESS_API_KEY`` is set in the environment; otherwise (or on any API
failure) falls back automatically to the deterministic, template-based
explanation — the script always produces output.
"""

from __future__ import annotations

import argparse
import sys

import _bootstrap  # noqa: F401
from app.services.disease.errors import DiseaseIntelligenceError
from app.services.explanation import default_provider, explain_top_n
from app.services.ml.model import ModelNotTrainedError
from app.services.ranking import rank_for_disease


def _print_explanation(explanation) -> None:
    print(f"\n{'=' * 70}")
    print(f"RANK {explanation.rank}  —  {explanation.drug_name}  "
          f"(repurposing score: {explanation.repurposing_score:.1f}/100)")
    print(f"{'=' * 70}")

    print("\nWHY PRIORITIZED")
    print(f"  {explanation.summary}")

    print("\nBIOLOGICAL EVIDENCE")
    for item in explanation.biological_evidence:
        print(f"  [{item.kind}] ({item.status}) {item.description}")

    print("\nML EVIDENCE")
    me = explanation.model_evidence
    print(f"  ({me.status}) {me.description}")

    print("\nLIMITATIONS")
    for line in explanation.limitations:
        print(f"  - {line}")

    prov = explanation.provenance
    print(f"\n  [provider: {prov.provider}"
          f"{f' / {prov.model_name}' if prov.model_name else ''}"
          f"{f' — fallback: {prov.fallback_reason}' if prov.fallback_reason else ''}]")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "disease", nargs="?", default="Glioblastoma",
        help='disease name, alias, or MONDO id (default: "Glioblastoma" / MONDO_0018177)',
    )
    parser.add_argument("--top-n", type=int, default=3, help="how many candidates to explain")
    args = parser.parse_args()

    provider = default_provider()
    print(f"Disease query: {args.disease!r}")
    print(f"Explanation provider: {provider.name}")

    try:
        ranked = rank_for_disease(args.disease, top_n=args.top_n)
    except ModelNotTrainedError:
        print("No trained model found. Train it first:\n    python scripts/train_model.py",
              file=sys.stderr)
        return 1
    except DiseaseIntelligenceError as exc:
        print(f"Could not resolve disease {args.disease!r}: {exc}", file=sys.stderr)
        return 1

    print(f"Disease: {ranked.disease_name} ({ranked.disease_id})")
    print(f"Explaining top {len(ranked.candidates)} of {ranked.provenance.n_ranked} "
          "ranked candidates...")

    explanations = explain_top_n(ranked, args.top_n, provider=provider)
    for explanation in explanations:
        _print_explanation(explanation)

    print(f"\n{ranked.provenance.disclaimer}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
