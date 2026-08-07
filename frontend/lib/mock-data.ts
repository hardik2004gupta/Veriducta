import type {
  DashboardStats,
  EvaluationMetrics,
  RetrievalTrace,
  StructuredAnswer,
  ReplayReport,
  ChartDataPoint,
} from "@/types";

// ── Dashboard stats ──────────────────────────────────────────────────────────

export const MOCK_DASHBOARD_STATS: DashboardStats = {
  total_queries: 4_832,
  avg_latency_ms: 3_240,
  avg_cost_usd: 0.0082,
  total_cost_usd: 39.62,
  faithfulness: 0.871,
  recall_at_5: 0.783,
  root_cause_accuracy: 0.733,
  omission_rate: 0.082,
  temporal_precision: 0.964,
  contradiction_ack_rate: 0.891,
  pipeline_up: true,
};

// ── Chart data (recharts-ready) ──────────────────────────────────────────────

function label(h: number): string {
  const d = new Date();
  d.setHours(d.getHours() - h);
  return `${String(d.getHours()).padStart(2, "0")}:00`;
}

function dayLabel(daysAgo: number): string {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  return `${d.getMonth() + 1}/${d.getDate()}`;
}

// Latency chart: {time, p50, p95}
export const MOCK_LATENCY_HISTORY = Array.from({ length: 24 }, (_, i) => ({
  time: label(23 - i),
  p50: Math.round(2800 + Math.sin(i * 0.6) * 600 + Math.random() * 300),
  p95: Math.round(6200 + Math.sin(i * 0.4) * 1200 + Math.random() * 600),
}));

// Cost chart: {date, cost}
export const MOCK_COST_HISTORY = Array.from({ length: 14 }, (_, i) => ({
  date: dayLabel(13 - i),
  cost: +(2.8 + Math.sin(i * 0.5) * 1.2 + Math.random() * 0.8).toFixed(2),
}));

// Faithfulness+recall chart: {date, faithfulness, recall}
export const MOCK_FAITHFULNESS_HISTORY = Array.from({ length: 30 }, (_, i) => ({
  date: dayLabel(29 - i),
  faithfulness: +(0.82 + Math.sin(i * 0.3) * 0.04 + Math.random() * 0.02).toFixed(3),
  recall: +(0.74 + Math.sin(i * 0.25) * 0.05 + Math.random() * 0.03).toFixed(3),
}));

// Root cause distribution
export const MOCK_ROOT_CAUSE_DISTRIBUTION: ChartDataPoint[] = [
  { name: "Retrieval", value: 38, color: "#06b6d4" },
  { name: "Generation", value: 28, color: "#8b5cf6" },
  { name: "Reranking", value: 19, color: "#f59e0b" },
  { name: "Chunking", value: 15, color: "#10b981" },
];

// ── Evaluation metrics ───────────────────────────────────────────────────────

export const MOCK_EVALUATION_METRICS: EvaluationMetrics = {
  run_id: "eval-20260807-001",
  retrieval: {
    recall_at_5: 0.783,
    recall_at_10: 0.851,
    mrr: 0.712,
    ndcg_at_10: 0.764,
    temporal_valid_retrieval_rate: 0.961,
    evidence_diversity: 3.2,
  },
  answer_quality: {
    claim_accuracy: 0.841,
    citation_entailment_rate: 0.871,
    omission_rate: 0.082,
    contradiction_acknowledgment_rate: 0.891,
  },
  causal_attribution: {
    root_cause_localization_accuracy: 0.733,
    realistic_boundary_error_accuracy: 0.680,
    chunking_ablation_recovery_rate: 0.612,
  },
  operational: {
    p50_latency_ms: 2_840,
    p95_latency_ms: 7_210,
    p99_latency_ms: 11_430,
    mean_cost_per_query_usd: 0.0082,
    cache_hit_rate: 0.234,
  },
  created_at: new Date().toISOString(),
};

// ── Retrieval trace ──────────────────────────────────────────────────────────

export const MOCK_RETRIEVAL_TRACE: RetrievalTrace = {
  trace_id: "trace-bca7f3d2-8e1a",
  query: "What are the permissible exposure limits for silica dust in construction?",
  query_date: "2024-01-15",
  top_k: 8,
  bm25_candidates: 100,
  dense_candidates: 100,
  after_rerank: 8,
  retrieval_latency_ms: 727,
  candidates: [
    {
      chunk_id: "osha-1926-1153-ch-0042",
      document_id: "osha-1926-1153",
      text: "The permissible exposure limit (PEL) for respirable crystalline silica in construction is 50 micrograms per cubic meter of air (50 μg/m³) as an 8-hour TWA.",
      text_excerpt: "The PEL for respirable crystalline silica in construction is 50 μg/m³ as an 8-hour TWA under 29 CFR 1926.1153.",
      bm25_score: 18.42,
      bm25_rank: 1,
      dense_score: 0.891,
      dense_rank: 1,
      rrf_score: 0.0322,
      rrf_rank: 1,
      rerank_score: 12.94,
      post_rerank_rank: 1,
      temporal_filter_rejected: false,
      rejection_reason: null,
      temporal_validity: "valid",
      page_number: 12,
      is_table: false,
      effective_date: "2017-09-23",
      token_count: 278,
    },
    {
      chunk_id: "osha-1926-1153-ch-0043",
      document_id: "osha-1926-1153",
      text: "Employers must use engineering controls and work practices to limit worker exposure to silica at or below the action level of 25 μg/m³ as an 8-hour TWA.",
      text_excerpt: "Action level of 25 μg/m³ (8-hr TWA) triggers mandatory engineering controls, medical surveillance, and written exposure control plans.",
      bm25_score: 14.7,
      bm25_rank: 2,
      dense_score: 0.843,
      dense_rank: 3,
      rrf_score: 0.0301,
      rrf_rank: 2,
      rerank_score: 11.22,
      post_rerank_rank: 2,
      temporal_filter_rejected: false,
      rejection_reason: null,
      temporal_validity: "valid",
      page_number: 13,
      is_table: false,
      effective_date: "2017-09-23",
      token_count: 312,
    },
    {
      chunk_id: "osha-1926-1153-ch-0087",
      document_id: "osha-1926-1153",
      text: "Table 1 provides specified exposure control methods for 18 common construction tasks involving silica-containing materials.",
      text_excerpt: "Table 1 — specified exposure control methods for 18 common construction tasks; compliance with Table 1 achieves PEL compliance without air monitoring.",
      bm25_score: 12.1,
      bm25_rank: 4,
      dense_score: 0.821,
      dense_rank: 4,
      rrf_score: 0.0284,
      rrf_rank: 3,
      rerank_score: 9.87,
      post_rerank_rank: 3,
      temporal_filter_rejected: false,
      rejection_reason: null,
      temporal_validity: "valid",
      page_number: 28,
      is_table: true,
      effective_date: "2017-09-23",
      token_count: 204,
    },
    {
      chunk_id: "osha-1910-1053-ch-0012",
      document_id: "osha-1910-1053",
      text: "General industry PEL for crystalline silica: 50 μg/m³ as an 8-hour TWA for respirable fraction.",
      text_excerpt: "29 CFR 1910.1053: general industry PEL 50 μg/m³ (8-hr TWA). Effective June 23, 2018 for general industry employers.",
      bm25_score: 11.3,
      bm25_rank: 5,
      dense_score: 0.804,
      dense_rank: 5,
      rrf_score: 0.0271,
      rrf_rank: 4,
      rerank_score: 8.43,
      post_rerank_rank: 4,
      temporal_filter_rejected: false,
      rejection_reason: null,
      temporal_validity: "valid",
      page_number: 6,
      is_table: false,
      effective_date: "2018-06-23",
      token_count: 256,
    },
  ],
  pre_rerank_top40: [],
  temporal_rejections: [
    {
      chunk_id: "osha-old-silica-ch-0003",
      document_id: "osha-old-silica",
      text: "Silica dust exposure limit: 10 mg/m³ (outdated 1971 standard).",
      text_excerpt: "Former OSHA silica PEL: 10 mg/m³ total dust (1971). Superseded by 1926.1153 (2016) and 1910.1053 (2016).",
      bm25_score: 9.1,
      bm25_rank: 7,
      dense_score: 0.762,
      dense_rank: 8,
      rrf_score: 0.0241,
      rrf_rank: 7,
      rerank_score: null,
      post_rerank_rank: null,
      temporal_filter_rejected: true,
      rejection_reason: "superseded",
      temporal_validity: "superseded",
      page_number: 4,
      is_table: false,
      effective_date: "1971-05-29",
      token_count: 189,
    },
  ],
  bm25_latency_ms: 34,
  dense_latency_ms: 281,
  rerank_latency_ms: 412,
  total_latency_ms: 843,
  created_at: new Date().toISOString(),
};

// ── Structured answer ────────────────────────────────────────────────────────

export const MOCK_ANSWER: StructuredAnswer = {
  answer_id: "ans-a7f3b291",
  query: "What are the permissible exposure limits for silica dust in construction?",
  summary:
    "OSHA's 29 CFR 1926.1153 sets a PEL of 50 μg/m³ (8-hour TWA) for respirable crystalline silica in construction, with an action level of 25 μg/m³ triggering mandatory engineering controls and medical surveillance.",
  claims: [
    {
      claim_id: "claim-001",
      text: "The permissible exposure limit for respirable crystalline silica in construction is 50 μg/m³ as an 8-hour TWA.",
      citation_chunk_id: "osha-1926-1153-ch-0042",
      excerpt: "The PEL for respirable crystalline silica in construction is 50 μg/m³ as an 8-hour TWA under 29 CFR 1926.1153.",
      key_entities: ["permissible exposure limit", "crystalline silica", "construction", "50 μg/m³"],
      confidence: "high",
      verification_status: "supported",
      nli_entailment_probability: 0.921,
      nli_contradiction_probability: 0.031,
      nli_neutral_probability: 0.048,
      requires_expert_review: false,
      counterevidence_chunk_ids: [],
    },
    {
      claim_id: "claim-002",
      text: "The action level triggering mandatory engineering controls is 25 μg/m³ as an 8-hour TWA.",
      citation_chunk_id: "osha-1926-1153-ch-0043",
      excerpt: "Action level of 25 μg/m³ as an 8-hour TWA.",
      key_entities: ["action level", "engineering controls", "25 μg/m³"],
      confidence: "high",
      verification_status: "supported",
      nli_entailment_probability: 0.887,
      nli_contradiction_probability: 0.042,
      nli_neutral_probability: 0.071,
      requires_expert_review: false,
      counterevidence_chunk_ids: [],
    },
    {
      claim_id: "claim-003",
      text: "Employers must maintain written exposure control plans and provide medical surveillance for affected workers.",
      citation_chunk_id: "osha-1926-1153-ch-0043",
      excerpt: "Employers must implement written exposure control plans and provide medical surveillance.",
      key_entities: ["exposure control plan", "medical surveillance"],
      confidence: "medium",
      verification_status: "ambiguous_conditional",
      nli_entailment_probability: 0.612,
      nli_contradiction_probability: 0.181,
      nli_neutral_probability: 0.207,
      requires_expert_review: true,
      counterevidence_chunk_ids: ["osha-1910-1053-ch-0012"],
    },
  ],
  citations: [
    {
      chunk_id: "osha-1926-1153-ch-0042",
      document_id: "osha-1926-1153",
      excerpt: "50 micrograms per cubic meter of air (50 μg/m³) as an 8-hour TWA",
      page_number: 12,
    },
    {
      chunk_id: "osha-1926-1153-ch-0043",
      document_id: "osha-1926-1153",
      excerpt: "action level of 25 μg/m³ as an 8-hour TWA",
      page_number: 13,
    },
  ],
  confidence: "high",
  confidence_tag: "high",
  input_tokens: 3_842,
  output_tokens: 487,
  estimated_cost_usd: 0.00731,
  cost_usd: 0.00731,
  latency_ms: 2_312,
  generation_latency_ms: 2_312,
  schema_validation_attempts: 1,
  requires_expert_review: true,
  retrieval_trace_id: "trace-bca7f3d2-8e1a",
  model: "claude-sonnet-4-6",
  config_snapshot_hash: "a3f7c291e84b2d5f9c1e3a7b4d8f2e6c",
  created_at: new Date().toISOString(),
};

// ── Replay report ────────────────────────────────────────────────────────────

export const MOCK_REPLAY_REPORT: ReplayReport = {
  report_id: "replay-d8a2c4f1",
  trace_id: "trace-bca7f3d2-8e1a",
  question_id: "qa-031",
  primary_root_cause: "retrieval",
  stage_attributions: {
    chunking: -0.02,
    retrieval: -0.31,
    reranking: -0.08,
    generation: -0.04,
  },
  heuristic_signals: [
    "Gold chunk osha-1926-1153-ch-0051 absent from pre-rerank top-40",
    "BM25 score for gold chunk < 5th percentile of returned candidates",
    "Temporal rejection removed 1 non-superseded chunk incorrectly",
  ],
  original_quality_score: 0.84,
  ablated_quality_score: 0.49,
  total_quality_delta: -0.35,
  created_at: new Date().toISOString(),
};

// ── Recent queries ───────────────────────────────────────────────────────────

export interface RecentQuery {
  id: string;
  query: string;
  latency_ms: number;
  cost_usd: number;
  faithfulness: number;
  root_cause: string | null;
  flagged: boolean;
  timestamp: string;
}

export const MOCK_RECENT_QUERIES: RecentQuery[] = [
  {
    id: "q-001",
    query: "What are the OSHA permissible exposure limits for silica dust?",
    latency_ms: 3241,
    cost_usd: 0.0073,
    faithfulness: 0.92,
    root_cause: null,
    flagged: false,
    timestamp: new Date(Date.now() - 120_000).toLocaleString(),
  },
  {
    id: "q-002",
    query: "What is the porosity classification for tight gas sands in geoscience logging?",
    latency_ms: 4812,
    cost_usd: 0.0091,
    faithfulness: 0.67,
    root_cause: "retrieval",
    flagged: true,
    timestamp: new Date(Date.now() - 480_000).toLocaleString(),
  },
  {
    id: "q-003",
    query: "Describe the NIST SP 800-53 audit and accountability control family",
    latency_ms: 2987,
    cost_usd: 0.0062,
    faithfulness: 0.88,
    root_cause: null,
    flagged: false,
    timestamp: new Date(Date.now() - 900_000).toLocaleString(),
  },
  {
    id: "q-004",
    query: "What superseded the 2019 fall protection standard for leading edge work?",
    latency_ms: 5634,
    cost_usd: 0.0112,
    faithfulness: 0.71,
    root_cause: "chunking",
    flagged: true,
    timestamp: new Date(Date.now() - 1_800_000).toLocaleString(),
  },
  {
    id: "q-005",
    query: "Explain the confined space rescue team requirements under 29 CFR 1910.146",
    latency_ms: 3109,
    cost_usd: 0.0068,
    faithfulness: 0.94,
    root_cause: null,
    flagged: false,
    timestamp: new Date(Date.now() - 3_600_000).toLocaleString(),
  },
];
