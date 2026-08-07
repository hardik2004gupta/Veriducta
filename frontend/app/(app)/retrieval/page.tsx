"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Search, Clock, Filter, ChevronDown, ChevronRight, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { MOCK_RETRIEVAL_TRACE } from "@/lib/mock-data";
import type { RetrievalCandidate } from "@/types";

// ── Score bar inline ──────────────────────────────────────────────────────────

function ScoreBar({ value, max, color }: { value: number | null | undefined; max: number; color: "cyan" | "violet" | "emerald" | "amber" }) {
  if (value === null || value === undefined) {
    return <span className="text-xs text-slate-700">—</span>;
  }
  return (
    <div className="flex items-center gap-2">
      <Progress value={value} max={max} color={color} className="w-24" />
      <span className="text-xs text-slate-300 tabular-nums w-12">{value.toFixed(4)}</span>
    </div>
  );
}

// ── Candidate row ─────────────────────────────────────────────────────────────

function CandidateRow({ candidate, rank, isRejected = false }: {
  candidate: RetrievalCandidate;
  rank: number;
  isRejected?: boolean;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className={cn("border-b border-white/[0.04] last:border-0 transition-colors", isRejected ? "opacity-50" : "hover:bg-white/[0.02]")}>
      <button onClick={() => setOpen(!open)} className="w-full flex items-center gap-4 px-5 py-3.5 text-left">
        {/* Rank */}
        <span className={cn("w-6 text-xs font-bold tabular-nums", isRejected ? "text-red-500" : "text-slate-400")}>
          {isRejected ? "✕" : `#${rank}`}
        </span>

        {/* Chunk ID */}
        <code className="text-xs text-cyan-300 w-52 shrink-0 truncate">{candidate.chunk_id}</code>

        {/* Text excerpt */}
        <span className="flex-1 text-xs text-slate-400 truncate">{candidate.text_excerpt}</span>

        {/* Scores */}
        <div className="flex items-center gap-6 shrink-0">
          <div className="w-32">
            <ScoreBar value={candidate.bm25_score} max={30} color="cyan" />
          </div>
          <div className="w-32">
            <ScoreBar value={candidate.dense_score} max={1} color="violet" />
          </div>
          <div className="w-32">
            <ScoreBar value={candidate.rrf_score} max={0.05} color="emerald" />
          </div>
          {candidate.rerank_score !== undefined && candidate.rerank_score !== null ? (
            <div className="w-32">
              <ScoreBar value={candidate.rerank_score} max={15} color="amber" />
            </div>
          ) : (
            <div className="w-32 text-xs text-slate-700">—</div>
          )}
        </div>

        {isRejected ? (
          <Badge variant="danger">
            <AlertCircle className="h-3 w-3" />
            {candidate.rejection_reason ?? "Rejected"}
          </Badge>
        ) : (
          open ? <ChevronDown className="h-4 w-4 text-slate-500" /> : <ChevronRight className="h-4 w-4 text-slate-500" />
        )}
      </button>

      {open && !isRejected && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="border-t border-white/[0.04] px-5 py-4 bg-white/[0.01]"
        >
          <div className="grid grid-cols-2 gap-8">
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Full Text Excerpt</p>
              <p className="text-sm text-slate-300 leading-relaxed">{candidate.text_excerpt}</p>
            </div>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Metadata</p>
                <div className="space-y-1.5">
                  {[
                    { label: "Document ID", value: candidate.document_id },
                    { label: "Temporal tag", value: candidate.temporal_validity ?? "valid" },
                    { label: "Token count", value: candidate.token_count?.toString() ?? "—" },
                    { label: "Post-rerank rank", value: candidate.post_rerank_rank?.toString() ?? "—" },
                  ].map(({ label, value }) => (
                    <div key={label} className="flex justify-between text-xs">
                      <span className="text-slate-500">{label}</span>
                      <span className="text-slate-300 font-mono">{value}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}

// ── Stage tabs ────────────────────────────────────────────────────────────────

const STAGES = ["BM25", "Dense", "RRF Fusion", "Temporal Filter", "Reranked"] as const;
type Stage = typeof STAGES[number];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function RetrievalInspectorPage() {
  const [query, setQuery] = useState("What are the OSHA permissible exposure limits for respirable crystalline silica?");
  const [stage, setStage] = useState<Stage>("Reranked");
  const [running, setRunning] = useState(false);

  const trace = MOCK_RETRIEVAL_TRACE;

  async function runQuery() {
    setRunning(true);
    await new Promise((r) => setTimeout(r, 1400));
    setRunning(false);
  }

  // Simulate per-stage candidate list
  const displayedCandidates = trace.candidates;

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        <h1 className="text-2xl font-black text-white">Retrieval Inspector</h1>
        <p className="text-sm text-slate-500 mt-1">Trace every candidate through BM25, dense retrieval, RRF fusion, temporal filtering, and cross-encoder reranking.</p>
      </motion.div>

      {/* Query bar */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.07 }}
        className="glass rounded-2xl p-4"
      >
        <div className="flex items-center gap-3">
          <Search className="h-4 w-4 text-slate-400 shrink-0" />
          <input
            className="flex-1 bg-transparent text-sm text-white placeholder-slate-600 focus:outline-none"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && runQuery()}
            placeholder="Enter a query to inspect retrieval…"
          />
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm">
              <Filter className="h-4 w-4" /> Filters
            </Button>
            <Button size="sm" onClick={runQuery} disabled={running}>
              {running ? "Running…" : "Run Retrieval"}
            </Button>
          </div>
        </div>
      </motion.div>

      {/* Stage metrics */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12 }}
        className="grid grid-cols-5 gap-3"
      >
        {[
          { label: "BM25 candidates", value: trace.bm25_candidates, color: "text-cyan-400" },
          { label: "Dense candidates", value: trace.dense_candidates, color: "text-violet-400" },
          { label: "After RRF", value: trace.bm25_candidates, color: "text-emerald-400" },
          { label: "After temporal filter", value: trace.bm25_candidates - trace.temporal_rejections.length, color: "text-amber-400" },
          { label: "Final (after rerank)", value: trace.after_rerank, color: "text-cyan-300" },
        ].map(({ label, value, color }) => (
          <div key={label} className="glass rounded-2xl p-4 text-center">
            <p className={`text-3xl font-black ${color}`}>{value}</p>
            <p className="text-xs text-slate-500 mt-1 leading-tight">{label}</p>
          </div>
        ))}
      </motion.div>

      {/* Stage selector + latency */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.16 }}
        className="flex items-center justify-between"
      >
        <div className="flex items-center gap-1 glass rounded-xl p-1">
          {STAGES.map((s) => (
            <button
              key={s}
              onClick={() => setStage(s)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
                stage === s ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/20" : "text-slate-500 hover:text-slate-300",
              )}
            >
              {s}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-4 text-xs text-slate-500">
          <div className="flex items-center gap-1.5">
            <div className="h-2 w-2 rounded-full bg-cyan-400" />
            <span>BM25 score</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-2 w-2 rounded-full bg-violet-400" />
            <span>Dense score</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-2 w-2 rounded-full bg-emerald-400" />
            <span>RRF score</span>
          </div>
          <div className="flex items-center gap-1.5">
            <div className="h-2 w-2 rounded-full bg-amber-400" />
            <span>Rerank score</span>
          </div>
          <div className="flex items-center gap-1.5">
            <Clock className="h-3.5 w-3.5" />
            <span>{trace.retrieval_latency_ms}ms total</span>
          </div>
        </div>
      </motion.div>

      {/* Candidate table */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="glass rounded-2xl overflow-hidden"
      >
        {/* Table header */}
        <div className="flex items-center gap-4 px-5 py-3 border-b border-white/[0.06] bg-white/[0.01]">
          <span className="w-6 text-xs text-slate-600">Rank</span>
          <span className="text-xs text-slate-600 w-52">Chunk ID</span>
          <span className="flex-1 text-xs text-slate-600">Text Excerpt</span>
          <div className="flex items-center gap-6 shrink-0">
            <span className="text-xs text-slate-600 w-32">BM25</span>
            <span className="text-xs text-slate-600 w-32">Dense</span>
            <span className="text-xs text-slate-600 w-32">RRF</span>
            <span className="text-xs text-slate-600 w-32">Rerank</span>
          </div>
          <span className="w-20" />
        </div>

        {/* Candidates */}
        {displayedCandidates.map((c, i) => (
          <CandidateRow key={c.chunk_id} candidate={c} rank={i + 1} />
        ))}

        {/* Temporal rejections */}
        {trace.temporal_rejections.length > 0 && (
          <>
            <div className="px-5 py-2 bg-red-500/5 border-t border-red-500/10">
              <p className="text-xs text-red-400 font-medium">Temporal Filter Rejections ({trace.temporal_rejections.length})</p>
            </div>
            {trace.temporal_rejections.map((c) => (
              <CandidateRow key={c.chunk_id} candidate={c} rank={0} isRejected />
            ))}
          </>
        )}
      </motion.div>

      {/* Score explanation */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
        className="glass rounded-2xl p-5"
      >
        <p className="text-sm font-semibold text-white mb-4">Score Computation</p>
        <div className="grid grid-cols-3 gap-4 text-xs">
          <div className="space-y-2">
            <p className="text-slate-500 uppercase tracking-wider font-medium">BM25</p>
            <code className="block bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-slate-300">
              score = Σ IDF(q) · tf(q,d) · (k1+1) / (tf(q,d) + k1·(1-b+b·|d|/avgdl))
            </code>
            <p className="text-slate-500">Okapi BM25 · top-100 · tokenised by whitespace</p>
          </div>
          <div className="space-y-2">
            <p className="text-slate-500 uppercase tracking-wider font-medium">RRF Fusion</p>
            <code className="block bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-slate-300">
              rrf(d) = Σ 1 / (k + rank(d,r)) · k=60
            </code>
            <p className="text-slate-500">Cormack et al. (2009) · implicit rank 101 for absent candidates</p>
          </div>
          <div className="space-y-2">
            <p className="text-slate-500 uppercase tracking-wider font-medium">Cross-encoder</p>
            <code className="block bg-white/[0.03] border border-white/[0.06] rounded-lg px-3 py-2 text-slate-300">
              ms-marco-MiniLM-L-12-v2 · top-40 input → top-8 output
            </code>
            <p className="text-slate-500">Raw logit score · single batch inference · CPU</p>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
