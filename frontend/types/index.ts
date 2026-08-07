// ── Core pipeline types ──────────────────────────────────────────────────────

export type VerificationStatus =
  | "supported"
  | "contradicted"
  | "ambiguous_conditional"
  | "not_searched"
  | "unresolved";

export type ConfidenceTag = "high" | "medium" | "low" | "uncertain";

export type RootCauseStage =
  | "chunking"
  | "retrieval"
  | "reranking"
  | "generation"
  | "unknown";

export type FailureMode =
  | "chunking_boundary"
  | "retrieval_miss"
  | "omission"
  | "temporal_confusion"
  | "hallucination"
  | "contradiction"
  | "none";

// ── Retrieval ────────────────────────────────────────────────────────────────

export interface RetrievalCandidate {
  chunk_id: string;
  document_id: string;
  text: string;
  text_excerpt?: string;
  bm25_score: number | null;
  bm25_rank: number | null;
  dense_score: number | null;
  dense_rank: number | null;
  rrf_score: number;
  rrf_rank: number;
  rerank_score: number | null;
  post_rerank_rank: number | null;
  temporal_filter_rejected: boolean;
  rejection_reason: string | null;
  temporal_validity?: string;
  page_number: number | null;
  is_table: boolean;
  effective_date: string | null;
  token_count?: number;
}

export interface RetrievalTrace {
  trace_id: string;
  query: string;
  query_date: string;
  top_k: number;
  candidates: RetrievalCandidate[];
  pre_rerank_top40: RetrievalCandidate[];
  temporal_rejections: RetrievalCandidate[];
  bm25_latency_ms: number;
  dense_latency_ms: number;
  rerank_latency_ms: number;
  total_latency_ms: number;
  created_at: string;
  // Computed aggregates (for UI display)
  bm25_candidates: number;
  dense_candidates: number;
  after_rerank: number;
  retrieval_latency_ms: number;
}

// ── Generation ───────────────────────────────────────────────────────────────

export interface Citation {
  chunk_id: string;
  document_id: string;
  excerpt: string;
  page_number: number | null;
}

export interface Claim {
  claim_id: string;
  text: string;
  citation_chunk_id: string;
  excerpt?: string;
  key_entities: string[];
  confidence: ConfidenceTag;
  verification_status: VerificationStatus;
  nli_entailment_probability: number | null;
  nli_contradiction_probability: number | null;
  nli_neutral_probability: number | null;
  requires_expert_review: boolean;
  counterevidence_chunk_ids: string[];
}

export interface StructuredAnswer {
  answer_id: string;
  query: string;
  summary: string;
  claims: Claim[];
  citations: Citation[];
  confidence: ConfidenceTag;
  confidence_tag: ConfidenceTag;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  cost_usd: number;
  latency_ms: number;
  generation_latency_ms: number;
  schema_validation_attempts: number;
  requires_expert_review: boolean;
  retrieval_trace_id: string;
  model: string;
  config_snapshot_hash: string;
  created_at: string;
}

// ── Replay ───────────────────────────────────────────────────────────────────

export interface StageAttribution {
  stage: RootCauseStage;
  quality_delta: number;
  confidence: number;
  description: string;
}

export interface ReplayReport {
  report_id: string;
  trace_id: string;
  question_id: string;
  primary_root_cause: RootCauseStage;
  stage_attributions: Record<string, number>;
  heuristic_signals: string[];
  original_quality_score: number;
  ablated_quality_score: number;
  total_quality_delta: number;
  created_at: string;
}

// ── Evaluation ───────────────────────────────────────────────────────────────

export interface RetrievalMetrics {
  recall_at_5: number;
  recall_at_10: number;
  mrr: number;
  ndcg_at_10: number;
  temporal_valid_retrieval_rate: number;
  evidence_diversity: number;
}

export interface AnswerQualityMetrics {
  claim_accuracy: number;
  citation_entailment_rate: number;
  omission_rate: number;
  contradiction_acknowledgment_rate: number;
}

export interface CausalAttributionMetrics {
  root_cause_localization_accuracy: number;
  realistic_boundary_error_accuracy: number;
  chunking_ablation_recovery_rate: number;
}

export interface OperationalMetrics {
  p50_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  mean_cost_per_query_usd: number;
  cache_hit_rate: number;
}

export interface EvaluationMetrics {
  run_id: string;
  retrieval: RetrievalMetrics;
  answer_quality: AnswerQualityMetrics;
  causal_attribution: CausalAttributionMetrics;
  operational: OperationalMetrics;
  created_at: string;
}

export interface RegressionViolation {
  condition: string;
  baseline_value: number;
  current_value: number;
  threshold: number;
  delta: number;
  is_blocking: boolean;
}

export interface RegressionResult {
  passed: boolean;
  violations: RegressionViolation[];
  summary: string;
}

// ── API responses ────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  timestamp: string;
  env: string;
}

export interface QueryRequest {
  query: string;
  query_date?: string;
  top_k?: number;
}

export interface QueryResponse {
  answer: StructuredAnswer;
  retrieval_trace: RetrievalTrace;
}

// ── UI state ─────────────────────────────────────────────────────────────────

export interface DashboardStats {
  total_queries: number;
  avg_latency_ms: number;
  avg_cost_usd: number;
  total_cost_usd: number;
  faithfulness: number;
  recall_at_5: number;
  root_cause_accuracy: number;
  omission_rate: number;
  temporal_precision: number;
  contradiction_ack_rate: number;
  pipeline_up: boolean;
}

export interface MetricPoint {
  timestamp: string;
  value: number;
}

export interface ChartDataPoint {
  name: string;
  value: number;
  color?: string;
}
