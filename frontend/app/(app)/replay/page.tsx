"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { GitBranch, ChevronRight, TrendingDown, TrendingUp, Target, AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { MOCK_REPLAY_REPORT } from "@/lib/mock-data";

// ── Stage card ────────────────────────────────────────────────────────────────

interface StageCardProps {
  stage: string;
  delta: number;
  isPrimary: boolean;
  description: string;
  index: number;
}

const STAGE_COLORS: Record<string, { label: string; color: string; bg: string }> = {
  chunking: { label: "Chunking", color: "text-amber-300", bg: "border-amber-500/20 bg-amber-500/5" },
  retrieval: { label: "Retrieval", color: "text-cyan-300", bg: "border-cyan-500/20 bg-cyan-500/5" },
  reranking: { label: "Reranking", color: "text-violet-300", bg: "border-violet-500/20 bg-violet-500/5" },
  generation: { label: "Generation", color: "text-emerald-300", bg: "border-emerald-500/20 bg-emerald-500/5" },
};

function StageCard({ stage, delta, isPrimary, description, index }: StageCardProps) {
  const cfg = STAGE_COLORS[stage] ?? { label: stage, color: "text-slate-300", bg: "border-white/10 bg-white/[0.02]" };
  const isNegative = delta < 0;

  return (
    <motion.div
      initial={{ opacity: 0, x: -16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.1 }}
      className={cn("rounded-2xl border p-5 relative", cfg.bg, isPrimary ? "ring-1 ring-red-500/30" : "")}
    >
      {isPrimary && (
        <div className="absolute -top-2.5 left-4 flex items-center gap-1.5 rounded-full bg-red-500/20 border border-red-500/30 px-2.5 py-0.5">
          <Target className="h-3 w-3 text-red-400" />
          <span className="text-xs text-red-300 font-semibold">Root Cause</span>
        </div>
      )}

      <div className="flex items-start justify-between mb-3">
        <div>
          <p className={`font-semibold text-sm ${cfg.color}`}>{cfg.label}</p>
          <p className="text-xs text-slate-500 mt-0.5">{description}</p>
        </div>
        <div className={cn("flex items-center gap-1 text-lg font-black", isNegative ? "text-red-400" : "text-emerald-400")}>
          {isNegative ? <TrendingDown className="h-5 w-5" /> : <TrendingUp className="h-5 w-5" />}
          {isNegative ? delta.toFixed(2) : `+${delta.toFixed(2)}`}
        </div>
      </div>

      {/* Attribution bar */}
      <div>
        <div className="flex justify-between text-xs mb-1.5">
          <span className="text-slate-500">Quality delta</span>
          <span className="text-slate-300">{Math.abs(delta * 100).toFixed(0)}% contribution</span>
        </div>
        <div className="h-2 w-full rounded-full bg-white/10 overflow-hidden">
          <div
            className={cn("h-full rounded-full", isNegative ? "bg-gradient-to-r from-red-500 to-red-400" : "bg-gradient-to-r from-emerald-500 to-emerald-400")}
            style={{ width: `${Math.min(100, Math.abs(delta) * 250)}%` }}
          />
        </div>
      </div>
    </motion.div>
  );
}

// ── Answer comparison ─────────────────────────────────────────────────────────

const ORIGINAL_ANSWER = `The permissible exposure limit (PEL) for respirable crystalline silica is 50 micrograms per cubic meter (μg/m³) as an 8-hour time-weighted average. This applies to all general industry operations under 29 CFR 1910.1053, effective June 23, 2016.`;

const ABLATED_ANSWER = `The permissible exposure limit for silica dust is 50 micrograms per cubic meter. Employers must reduce exposures to this level.`;

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ReplayViewerPage() {
  const [selectedCase, setSelectedCase] = useState(0);
  const report = MOCK_REPLAY_REPORT;

  const STAGE_DESCRIPTIONS: Record<string, string> = {
    chunking: "Boundary-naive vs boundary-aware chunking; Recall@5 delta on document-specific collections",
    retrieval: "Gold supporting chunks injected; quality delta measures retrieval contribution",
    reranking: "Pre-rerank top-40 reconstructed at cutoffs top-1/3/5/8; no re-inference needed",
    generation: "Historical retrieval context replayed with baseline system prompt",
  };

  const CASES = [
    { id: "qa-031", question: "OSHA PEL for respirable crystalline silica?", primaryCause: "retrieval" },
    { id: "qa-017", question: "NIST uncertainty propagation for indirect measurements?", primaryCause: "chunking" },
    { id: "qa-044", question: "Seismic site classification criteria for Site Class D?", primaryCause: "reranking" },
    { id: "qa-009", question: "Confined space entry permit requirements OSHA 1910.146?", primaryCause: "generation" },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black text-white">Replay Viewer</h1>
            <p className="text-sm text-slate-500 mt-1">Four-stage causal ablation · quality delta attribution · root cause localization</p>
          </div>
          <Badge variant="warning">
            <GitBranch className="h-3.5 w-3.5" />
            60-case benchmark · 73.3% accuracy
          </Badge>
        </div>
      </motion.div>

      <div className="grid grid-cols-12 gap-4">
        {/* Case list */}
        <div className="col-span-3">
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-3">Corruption Cases</p>
          <div className="glass rounded-2xl overflow-hidden">
            {CASES.map((c, i) => (
              <button
                key={c.id}
                onClick={() => setSelectedCase(i)}
                className={cn(
                  "w-full flex items-start gap-3 px-4 py-3.5 text-left border-b border-white/[0.04] last:border-0 transition-colors",
                  selectedCase === i ? "bg-white/[0.04]" : "hover:bg-white/[0.02]",
                )}
              >
                <code className="text-xs text-slate-500 mt-0.5 shrink-0">{c.id}</code>
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">{c.question}</p>
                  <div className={cn("mt-1.5 text-[10px] font-medium uppercase tracking-wider", STAGE_COLORS[c.primaryCause]?.color)}>
                    {c.primaryCause}
                  </div>
                </div>
                {selectedCase === i && <ChevronRight className="h-4 w-4 text-cyan-400 shrink-0 mt-0.5" />}
              </button>
            ))}
          </div>
        </div>

        {/* Ablation detail */}
        <div className="col-span-9 space-y-4">
          {/* Question */}
          <motion.div
            key={selectedCase}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="glass rounded-2xl p-5"
          >
            <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Question · {CASES[selectedCase].id}</p>
            <p className="text-white font-medium">{CASES[selectedCase].question}</p>
          </motion.div>

          {/* Stage attributions */}
          <div className="grid grid-cols-2 gap-3">
            {Object.entries(report.stage_attributions).map(([stage, delta], i) => (
              <StageCard
                key={stage}
                stage={stage}
                delta={delta}
                isPrimary={stage === report.primary_root_cause}
                description={STAGE_DESCRIPTIONS[stage] ?? ""}
                index={i}
              />
            ))}
          </div>

          {/* Root cause summary */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 }}
            className="glass rounded-2xl p-5 border border-red-500/10"
          >
            <div className="flex items-center gap-3 mb-4">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-red-500/10 border border-red-500/20">
                <AlertTriangle className="h-5 w-5 text-red-400" />
              </div>
              <div>
                <p className="font-semibold text-white">Primary Root Cause: <span className="text-red-300 capitalize">{report.primary_root_cause}</span></p>
                <p className="text-xs text-slate-500">Stage 2 (retrieval) ablation produced the largest quality delta</p>
              </div>
            </div>

            <div className="grid grid-cols-4 gap-3">
              {Object.entries(report.stage_attributions).map(([stage, delta]) => {
                const total = Object.values(report.stage_attributions).reduce((s, v) => s + Math.abs(v), 0);
                const pct = Math.abs(delta) / total;
                return (
                  <div key={stage}>
                    <div className="flex justify-between text-xs mb-1">
                      <span className={STAGE_COLORS[stage]?.color ?? "text-slate-300"}>{STAGE_COLORS[stage]?.label ?? stage}</span>
                      <span className="text-slate-400">{(pct * 100).toFixed(0)}%</span>
                    </div>
                    <Progress value={pct} color={
                      stage === "chunking" ? "amber" :
                      stage === "retrieval" ? "cyan" :
                      stage === "reranking" ? "violet" : "emerald"
                    } />
                  </div>
                );
              })}
            </div>
          </motion.div>

          {/* Answer comparison */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="grid grid-cols-2 gap-4"
          >
            <div className="glass rounded-2xl p-5">
              <div className="flex items-center gap-2 mb-3">
                <div className="h-2 w-2 rounded-full bg-emerald-400" />
                <p className="text-xs font-semibold text-emerald-400 uppercase tracking-wider">Original Answer</p>
              </div>
              <p className="text-sm text-slate-300 leading-relaxed">{ORIGINAL_ANSWER}</p>
              <div className="mt-3 flex items-center gap-2">
                <Badge variant="success">Quality 0.74</Badge>
                <Badge variant="muted">3 claims</Badge>
              </div>
            </div>
            <div className="glass rounded-2xl p-5 border border-red-500/10">
              <div className="flex items-center gap-2 mb-3">
                <div className="h-2 w-2 rounded-full bg-red-400" />
                <p className="text-xs font-semibold text-red-400 uppercase tracking-wider">After Retrieval Corruption</p>
              </div>
              <p className="text-sm text-slate-400 leading-relaxed">{ABLATED_ANSWER}</p>
              <div className="mt-3 flex items-center gap-2">
                <Badge variant="danger">Quality 0.43</Badge>
                <Badge variant="muted">1 claim</Badge>
              </div>
            </div>
          </motion.div>

          {/* Quality delta bar */}
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.55 }}
            className="glass rounded-2xl p-5"
          >
            <div className="flex items-center justify-between mb-3">
              <p className="text-sm font-semibold text-white">Quality Delta</p>
              <div className="flex items-center gap-2 text-sm">
                <span className="text-emerald-400">0.74</span>
                <span className="text-slate-600">→</span>
                <span className="text-red-400">0.43</span>
                <Badge variant="danger">−0.31</Badge>
              </div>
            </div>
            <div className="h-3 w-full rounded-full bg-white/10 overflow-hidden">
              <div className="h-full flex">
                <div className="bg-gradient-to-r from-emerald-500 to-emerald-400 rounded-l-full" style={{ width: "74%" }} />
                <div className="bg-gradient-to-r from-red-500/30 to-red-400/10 flex-1 rounded-r-full" />
              </div>
            </div>
            <div className="flex justify-between text-xs text-slate-500 mt-1.5">
              <span>0</span>
              <span className="text-red-400">−0.31 from retrieval corruption</span>
              <span>1.0</span>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
