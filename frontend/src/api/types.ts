/**
 * TypeScript mirrors of the backend's Pydantic response schemas.
 *
 * Field names match the backend exactly (snake_case, no renaming) so this
 * file stays a direct, checkable mirror of `app/models/*.py` /
 * `app/api/schemas.py` — never a place to invent a new shape. Every value
 * here is displayed as returned; nothing is recalculated on this side.
 */

// -- Phase 7: evidence fusion -------------------------------------------

export type EvidenceComponentName = "gene_target" | "pathway" | "ml";

export interface EvidenceComponent {
  name: EvidenceComponentName;
  available: boolean;
  value: number | null;
  configured_weight: number;
  effective_weight: number | null;
  contribution_points: number | null;
  calculation_method: string;
  supporting: Record<string, unknown>;
  provenance: string;
  unavailable_reason: string | null;
}

export interface SideEffectContext {
  side_effect_count: number;
  has_sider_evidence: boolean;
  note: string;
}

export interface DrugCharacterizationContext {
  drug_target_count: number;
  drug_pathway_count: number;
  mechanism_count: number;
  action_type_counts: Record<string, number>;
  note: string;
}

export interface FusionProvenance {
  scoring_version: string;
  feature_schema_version: string | null;
  prediction_schema_version: string | null;
  weight_scheme: string;
  normalization: string;
  missing_evidence_policy: string;
  double_counting_policy: string;
  disclaimer: string;
}

export interface EvidenceFusionResult {
  disease_id: string;
  drug_id: string;
  disease_name: string;
  drug_name: string;
  repurposing_score: number;
  score_scale: string;
  components: EvidenceComponent[];
  n_components_available: number;
  n_components_unavailable: number;
  weights_configured: Record<string, number>;
  weights_renormalized_over_available: boolean;
  side_effect_context: SideEffectContext;
  drug_characterization: DrugCharacterizationContext;
  matched_gene_hgnc_ids: string[];
  matched_disease_gene_ids: string[];
  matched_drug_target_ids: string[];
  matched_pathway_reactome_ids: string[];
  generation_methods: string[];
  ml_model_name: string | null;
  ml_model_output: number | null;
  ml_baseline_output: number | null;
  scoring_version: string;
  provenance: FusionProvenance;
  interpretation: string;
}

// -- Phase 8: ranking -----------------------------------------------------

export interface RankedCandidate {
  rank: number;
  disease_id: string;
  drug_id: string;
  disease_name: string;
  drug_name: string;
  repurposing_score: number;
  matched_gene_hgnc_ids: string[];
  matched_disease_gene_ids: string[];
  matched_drug_target_ids: string[];
  matched_pathway_reactome_ids: string[];
  generation_methods: string[];
  fusion: EvidenceFusionResult;
}

export interface RankingProvenance {
  ranking_version: string;
  ranking_signal: string;
  tie_breaker: string;
  scores_recalculated: boolean;
  biology_recalculated: boolean;
  n_input: number;
  n_ranked: number;
  top_n_requested: number | null;
  top_n_applied: number | null;
  scoring_version: string | null;
  disclaimer: string;
  interpretation: string;
}

export interface RankedCandidateResult {
  disease_id: string | null;
  disease_name: string | null;
  candidates: RankedCandidate[];
  n_candidates: number;
  provenance: RankingProvenance;
}

// -- Phase 9: explanation ---------------------------------------------------

export type EvidenceStatus = "supported" | "assessed_no_support" | "not_assessed";

export interface BiologicalEvidenceItem {
  kind: "gene_target" | "pathway";
  status: EvidenceStatus;
  value: number | null;
  contribution_points: number | null;
  supporting_ids: string[];
  description: string;
}

export interface ModelEvidence {
  status: EvidenceStatus;
  model_name: string | null;
  model_output: number | null;
  baseline_output: number | null;
  contribution_points: number | null;
  top_feature_names: string[];
  description: string;
}

export interface ExplanationProvenance {
  explanation_version: string;
  provider: "deepseek_featherless" | "deterministic_fallback";
  model_name: string | null;
  generated_at: string;
  scoring_version: string;
  ranking_version: string;
  fallback_reason: string | null;
  validation_notes: string[];
  grounding_note: string;
  disclaimer: string;
}

export interface CandidateExplanation {
  disease_id: string;
  drug_id: string;
  disease_name: string;
  drug_name: string;
  rank: number;
  repurposing_score: number;
  summary: string;
  biological_evidence: BiologicalEvidenceItem[];
  model_evidence: ModelEvidence;
  limitations: string[];
  provenance: ExplanationProvenance;
}

// -- Phase 10: evidence graph -----------------------------------------------

export type GraphNodeType =
  | "disease"
  | "disease_gene"
  | "drug"
  | "drug_target"
  | "pathway"
  | "prediction"
  | "evidence_component"
  | "score"
  | "rank"
  | "explanation";

export type GraphEdgeType =
  | "associated_with"
  | "matched_to"
  | "has_target"
  | "participates_in"
  | "received"
  | "ranked"
  | "explained_by";

export interface GraphNode {
  id: string;
  type: GraphNodeType;
  label: string;
  metadata: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: GraphEdgeType;
  metadata: Record<string, unknown>;
  provenance: string | null;
}

export interface EvidenceGraphMetadata {
  graph_schema_version: string;
  n_nodes: number;
  n_edges: number;
  n_candidates: number;
  includes_ml_evidence: boolean;
  includes_explanation: boolean;
  node_type_counts: Record<string, number>;
  edge_type_counts: Record<string, number>;
  disclaimer: string;
  interpretation: string;
}

export interface EvidenceGraph {
  disease_id: string;
  disease_name: string;
  drug_id: string | null;
  drug_ids: string[];
  nodes: GraphNode[];
  edges: GraphEdge[];
  metadata: EvidenceGraphMetadata;
}

// -- Level 2: disease intelligence (standalone profile) ---------------------

export interface ExternalIdentifier {
  external_id: string;
  source: string;
  is_primary: boolean;
}

export interface GeneAssociation {
  gene_id: string;
  gene_name: string | null;
  ensembl_id: string | null;
  association_score: number | null;
  source: string;
}

export interface PathwayAssociation {
  pathway_id: string;
  pathway_name: string;
  reactome_id: string | null;
  gene_support_count: number | null;
  association_score: number | null;
  source: string;
}

export interface DiseaseMolecularProfile {
  gene_count: number;
  pathway_count: number;
  mean_gene_association_score: number | null;
  max_gene_association_score: number | null;
  top_gene_symbols: string[];
  top_pathway_names: string[];
  genes_truncated: boolean;
}

export interface DiseaseProfileProvenance {
  disease_source: string;
  datasets_used: string[];
  gene_source: string;
  gene_score_semantics: string;
  genes_capped_per_disease: number;
  genes_truncated: boolean;
  pathway_source: string;
  pathway_derivation: string;
  pathway_min_gene_support: number;
  snapshot_note: string;
  disclaimer: string;
}

export interface DiseaseProfile {
  disease_id: string;
  disease_name: string;
  ontology_id: string | null;
  external_identifiers: ExternalIdentifier[];
  genes: GeneAssociation[];
  pathways: PathwayAssociation[];
  molecular_profile: DiseaseMolecularProfile;
  provenance: DiseaseProfileProvenance;
  summary_text: string;
}

// -- Level 3: drug intelligence (standalone profile) -------------------------

export interface SideEffect {
  side_effect_id: string;
  side_effect_name: string;
  umls_cui: string | null;
  source: string;
}

export interface DrugTargetAssociation {
  target_id: string;
  target_name: string | null;
  target_type: string | null;
  uniprot_id: string | null;
  action_type: string | null;
  source: string;
}

export interface MechanismOfAction {
  target_id: string;
  target_name: string | null;
  action_type: string | null;
  description: string;
  source: string;
}

export interface PathwayContext {
  reactome_id: string;
  pathway_name: string;
  supporting_target_count: number;
  supporting_uniprot_ids: string[];
  source: string;
}

export interface DrugBiologicalContext {
  proteins: string[];
  pathways: PathwayContext[];
  pathway_context_available: boolean;
  unavailable_reason: string | null;
}

export interface DrugProvenance {
  identity_source: string;
  side_effect_source: string;
  target_source: string;
  mechanism_source: string;
  target_coverage_note: string;
  pathway_source: string;
  pathway_derivation: string;
  datasets_used: string[];
  optional_sources_used: string[];
  optional_sources_skipped: Record<string, string>;
  snapshot_note: string;
  disclaimer: string;
}

export interface DrugProfile {
  drug_id: string;
  drug_name: string;
  canonical_identifier: string | null;
  chembl_id: string | null;
  pubchem_cid: string | null;
  external_identifiers: ExternalIdentifier[];
  side_effects: SideEffect[];
  side_effect_count: number;
  targets: DrugTargetAssociation[];
  target_count: number;
  mechanisms: MechanismOfAction[];
  biological_context: DrugBiologicalContext;
  provenance: DrugProvenance;
  summary_text: string;
}

export type DrugMatchType = "internal_id" | "external_id" | "exact_name";

export interface DrugMatch {
  drug_id: string;
  drug_name: string;
  chembl_id: string | null;
  pubchem_cid: string | null;
  matched_on: DrugMatchType;
  matched_value: string;
}

export interface AmbiguousDrugDetail {
  status: "ambiguous";
  query: string;
  candidates: DrugMatch[];
  message: string;
}

export interface UnsupportedDrugDetail {
  status: "not_supported";
  query: string;
  suggestions: string[];
  message: string;
}

// -- Phase 11: dashboard API -------------------------------------------------

export interface DiseaseOverview {
  disease_id: string;
  disease_name: string;
  ontology_id: string | null;
  gene_count: number;
  pathway_count: number;
  genes_truncated: boolean;
  summary_text: string;
}

export interface CandidateSummary {
  candidates_discovered: number;
  candidates_ranked: number;
  counts_by_method: Record<string, number>;
  n_with_gene_target_evidence: number;
  n_with_pathway_evidence: number;
  n_with_ml_evidence: number;
}

export interface PipelineRunResponse {
  disease: DiseaseOverview;
  candidate_summary: CandidateSummary;
  ranked: RankedCandidateResult;
  disclaimer: string;
}

export type DiseaseMatchType = "internal_id" | "ontology_id" | "exact_name" | "alias";

export interface DiseaseMatch {
  disease_id: string;
  disease_name: string;
  ontology_id: string | null;
  matched_on: DiseaseMatchType;
  matched_value: string;
}

export interface AmbiguousDiseaseDetail {
  status: "ambiguous";
  query: string;
  candidates: DiseaseMatch[];
  message: string;
}

export interface UnsupportedDiseaseDetail {
  status: "not_supported";
  query: string;
  suggestions: string[];
  message: string;
}

export interface EmptyQueryDetail {
  status: "empty_query";
  message: string;
}

export interface PlainDetail {
  message: string;
  disease_id?: string;
  drug_id?: string;
}
