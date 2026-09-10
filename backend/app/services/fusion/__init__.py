"""Evidence Fusion + Repurposing Score (Phase 7).

    CandidateDrug + FeatureVector + (optional) PredictionResult
        -> fuse_evidence(...)  ->  EvidenceFusionResult

Combines the independent evidence families (gene-target, pathway, ML) into one
transparent 0-100 **internal research prioritization score**, keeping every
component visible. Missing evidence is excluded and the weights renormalized —
it is never treated as negative evidence. Side effects and drug characterization
are kept as descriptive context, not scored.

`repurposing_score` != clinical efficacy != treatment probability != medical
recommendation. Phase 7 does NOT rank.
"""

from app.models.fusion import (
    SCORING_VERSION,
    DrugCharacterizationContext,
    EvidenceComponent,
    EvidenceFusionResult,
    FusionProvenance,
    SideEffectContext,
)
from app.services.fusion.config import DEFAULT_CONFIG, FusionConfig
from app.services.fusion.errors import (
    EvidenceFusionError,
    InconsistentFusionInputError,
)
from app.services.fusion.fuse import fuse_all, fuse_evidence, fuse_for_disease

__all__ = [
    "DEFAULT_CONFIG",
    "SCORING_VERSION",
    "DrugCharacterizationContext",
    "EvidenceComponent",
    "EvidenceFusionError",
    "EvidenceFusionResult",
    "FusionConfig",
    "FusionProvenance",
    "InconsistentFusionInputError",
    "SideEffectContext",
    "fuse_all",
    "fuse_evidence",
    "fuse_for_disease",
]
