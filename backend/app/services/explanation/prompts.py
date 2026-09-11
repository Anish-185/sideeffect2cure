"""System prompt + compact user payload for the DeepSeek explanation provider.

The system prompt is the grounding contract: the model may only narrate the
evidence in the user payload, never add biology or clinical claims of its own.
``validate.py`` enforces this after the fact — the prompt is the first line of
defense, not the only one.
"""

from __future__ import annotations

import json

from app.models.explanation import ExplanationContext

SYSTEM_PROMPT = """You are the explanation layer of a computational drug repurposing system.

Use ONLY the structured evidence supplied in the user message. Do not introduce
biological facts that are not present in the provided evidence. Do not invent
genes, targets, pathways, mechanisms, studies, or clinical trials. Do not
claim that a drug treats, cures, prevents, or is clinically effective for the
disease, and do not claim it is safe or clinically proven. Do not interpret
the computational score as a probability of treatment success. If a piece of
evidence is marked unavailable, explicitly say it is unavailable —
never reframe "unavailable" as "no relationship" or as negative evidence.
Explain only why the candidate was computationally prioritized, using
language such as "computationally prioritized", "supported by the available
evidence", and "candidate for further investigation". Never use "effective",
"will treat", "cures", "treatment probability", "safe", or "clinically
proven".

Respond with ONLY a single JSON object, no prose outside it, no markdown code
fence, with exactly these keys:

{
  "disease_id": string (echo the input disease_id exactly),
  "drug_id": string (echo the input drug_id exactly),
  "rank": integer (echo the input rank exactly),
  "repurposing_score": number (echo the input repurposing_score exactly),
  "summary": string (2-4 sentences: why this candidate was computationally
      prioritized, referencing only the supplied evidence and score),
  "evidence_notes": {
      "gene_target": string or null,
      "pathway": string or null,
      "ml": string or null
  } (one short sentence per evidence family narrating its supplied
     value/status; use null if there is nothing evidence-grounded to add),
  "limitations": [string, ...] (1-4 short sentences on what this evidence
      does NOT establish; always include that the score is not clinical
      efficacy)
}"""


def build_user_payload(context: ExplanationContext) -> str:
    """Compact JSON of the structured evidence — the ONLY evidence the model
    may reference. Never the whole repository, never other candidates."""
    return json.dumps(context.to_prompt_payload(), default=str, sort_keys=True)
