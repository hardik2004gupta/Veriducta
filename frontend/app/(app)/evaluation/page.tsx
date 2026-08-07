"use client";

import { motion } from "framer-motion";
import { BarChart3, CheckCircle2, XCircle, AlertTriangle, TrendingUp, TrendingDown, Shield } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Card, CardHeader, CardTitle, CardValue } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { MOCK_EVALUATION_METRICS, MOCK_FAITHFULNESS_HISTORY } from "@/lib/mock-data";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";

// ── Regression gate ───────────────────────────────────────────────────────────

const REGRESSION_GATES = [
  { label: "Faithfulness drop", threshold: ">2% from baseline", current: "+0.8%", passing: true },
  { label: "Recall@5 drop", threshold: ">3% from baseline", current: "+1.2%", passing: true },
  { label: "p95 latency increase", threshold: ">20% from baseline", current: "+4.1%", passing: true },
  { label: "Root-cause accuracy drop", threshold: ">5% from baseline", current: "+3.1%", passing: true },
  { label: "Unauthorized evidence exposure", threshold: ">0%", current: "0%", passing: true },
];

// ── RAGAS comparison ──────────────────────────────────────────────────────────

const RAGAS_ROWS = [
  { metric: "Faithfulness (citation entailment)", ragas: "0.82", ours: "0.871", better: true },
  { metric: "Context Recall", ragas: "0.74", ours: "0.783", better: true },
  { metric: "Omission Rate", ragas: "-", ours: "8.2%", better: true, exclusive: true },
  { metric: "Causal Attribution Accuracy", ragas: "-", ours: "73.3%", better: true, exclusive: true },
  { metric: "Temporal-Valid Retrieval Rate", ragas: "-", ours: "96.4%", better: true, exclusive: true },
  { metric: "Contradiction Acknowledgment Rate", ragas: "-", ours: "89.1%", better: true, exclusive: true },
];

// ── Radar chart data ──────────────────────────────────────────────────────────

const RADAR_DATA = [
  { axis: "Faithfulness", value: 87.1, baseline: 82 },
  { axis: "Recall@5", value: 78.3, baseline: 74 },
  { axis: "Root-Cause Acc.", value: 73.3, baseline: 0 },
  { axis: "Omission Rate*", value: 91.8, baseline: 0 },
  { axis: "Temporal Prec.", value: 96.4, baseline: 0 },
  { axis: "Contradiction Ack.", value: 89.1, baseline: 0 },
];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function EvaluationPage() {
  const metrics = MOCK_EVALUATION_METRICS;

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black text-white">Evaluation Dashboard</h1>
            <p className="text-sm text-slate-500 mt-1">40-question golden QA · 60-case corruption benchmark · RAGAS baseline comparison</p>
          </div>
          <Badge variant="success">
            <CheckCircle2 className="h-3.5 w-3.5" />
            All regression gates passing
          </Badge>
        </div>
      </motion.div>

      {/* Top metrics */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.07 }}
        className="grid grid-cols-4 gap-4"
      >
        {[
          { label: "Faithfulness", value: `${(metrics.answer_quality.citation_entailment_rate * 100).toFixed(1)}%`, icon: Shield, color: "emerald" as const, sub: "citation entailment rate" },
          { label: "Recall@5", value: `${(metrics.retrieval.recall_at_5 * 100).toFixed(1)}%`, icon: BarChart3, color: "cyan" as const, sub: "golden QA set" },
          { label: "Root-Cause Accuracy", value: `${(metrics.causal_attribution.root_cause_localization_accuracy * 100).toFixed(1)}%`, icon: TrendingUp, color: "violet" as const, sub: "60-case benchmark" },
          { label: "p95 Latency", value: `${(metrics.operational.p95_latency_ms / 1000).toFixed(1)}s`, icon: AlertTriangle, color: "amber" as const, sub: "end-to-end query" },
        ].map(({ label, value, icon: Icon, color, sub }) => (
          <Card key={label}>
            <CardHeader>
              <CardTitle>{label}</CardTitle>
              <div className={cn("flex h-9 w-9 items-center justify-center rounded-xl",
                color === "emerald" ? "text-emerald-400 bg-emerald-500/10" :
                color === "cyan" ? "text-cyan-400 bg-cyan-500/10" :
                color === "violet" ? "text-violet-400 bg-violet-500/10" :
                "text-amber-400 bg-amber-500/10"
              )}>
                <Icon className="h-4.5 w-4.5" />
              </div>
            </CardHeader>
            <CardValue>{value}</CardValue>
            <p className="mt-1 text-xs text-slate-500">{sub}</p>
          </Card>
        ))}
      </motion.div>

      {/* CI Regression gate */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12 }}
        className="glass rounded-2xl overflow-hidden"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
          <p className="font-semibold text-white text-sm">CI Regression Gate</p>
          <Badge variant="success">5/5 passing</Badge>
        </div>
        <div className="divide-y divide-white/[0.04]">
          {REGRESSION_GATES.map((g) => (
            <div key={g.label} className="flex items-center gap-4 px-5 py-3">
              {g.passing ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
              ) : (
                <XCircle className="h-4 w-4 text-red-400 shrink-0" />
              )}
              <span className="flex-1 text-sm text-slate-300">{g.label}</span>
              <span className="text-xs text-slate-500">threshold: {g.threshold}</span>
              <span className={cn("text-sm font-semibold tabular-nums", g.passing ? "text-emerald-400" : "text-red-400")}>
                {g.current}
              </span>
            </div>
          ))}
        </div>
      </motion.div>

      {/* Charts row */}
      <div className="grid grid-cols-12 gap-4">
        {/* Radar */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.17 }}
          className="col-span-5 glass rounded-2xl p-5"
        >
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="font-semibold text-white text-sm">Metric Coverage</p>
              <p className="text-xs text-slate-500">Veriducta vs RAGAS baseline</p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              <div className="flex items-center gap-1.5">
                <div className="h-2 w-2 rounded-full bg-cyan-400" />
                <span className="text-slate-400">Veriducta</span>
              </div>
              <div className="flex items-center gap-1.5">
                <div className="h-2 w-2 rounded-full bg-slate-600" />
                <span className="text-slate-400">RAGAS</span>
              </div>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <RadarChart data={RADAR_DATA}>
              <PolarGrid stroke="rgba(255,255,255,0.06)" />
              <PolarAngleAxis dataKey="axis" tick={{ fill: "#475569", fontSize: 10 }} />
              <Radar name="Veriducta" dataKey="value" stroke="#06b6d4" fill="#06b6d4" fillOpacity={0.15} strokeWidth={2} />
              <Radar name="RAGAS" dataKey="baseline" stroke="#64748b" fill="#64748b" fillOpacity={0.08} strokeWidth={1} strokeDasharray="4 4" />
            </RadarChart>
          </ResponsiveContainer>
          <p className="text-[10px] text-slate-600 text-center">*Omission Rate shown as 100% − omission_rate (inverted for radar)</p>
        </motion.div>

        {/* RAGAS comparison table */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="col-span-7 glass rounded-2xl overflow-hidden"
        >
          <div className="px-5 py-4 border-b border-white/[0.06] flex items-center justify-between">
            <p className="font-semibold text-white text-sm">RAGAS Comparison</p>
            <Badge variant="muted">4 exclusive metrics</Badge>
          </div>
          <div>
            <div className="grid grid-cols-4 gap-4 px-5 py-2 border-b border-white/[0.04]">
              <span className="col-span-2 text-xs text-slate-600">Metric</span>
              <span className="text-xs text-slate-600 text-center">RAGAS</span>
              <span className="text-xs text-slate-600 text-center">Veriducta</span>
            </div>
            {RAGAS_ROWS.map((row, i) => (
              <div key={row.metric} className={cn("grid grid-cols-4 gap-4 px-5 py-3 border-b border-white/[0.03] last:border-0", i % 2 === 0 ? "bg-white/[0.01]" : "")}>
                <div className="col-span-2 flex items-center gap-2">
                  <span className="text-sm text-slate-300">{row.metric}</span>
                  {row.exclusive && <Badge variant="muted" className="text-[10px] px-1.5 py-0">exclusive</Badge>}
                </div>
                <div className="flex items-center justify-center">
                  {row.ragas === "-" ? (
                    <span className="text-slate-700 text-sm">-</span>
                  ) : (
                    <span className="text-sm text-slate-400 font-mono">{row.ragas}</span>
                  )}
                </div>
                <div className="flex items-center justify-center gap-2">
                  <span className="text-sm text-emerald-400 font-semibold font-mono">{row.ours}</span>
                  {row.better && row.ragas !== "-" && (
                    <TrendingUp className="h-3.5 w-3.5 text-emerald-400" />
                  )}
                  {row.exclusive && (
                    <CheckCircle2 className="h-3.5 w-3.5 text-cyan-400" />
                  )}
                </div>
              </div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Metric history */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
        className="glass rounded-2xl p-5"
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="font-semibold text-white text-sm">Metric History</p>
            <p className="text-xs text-slate-500">30-day faithfulness + recall trend</p>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={160}>
          <AreaChart data={MOCK_FAITHFULNESS_HISTORY} margin={{ top: 5, right: 0, left: -30, bottom: 0 }}>
            <defs>
              <linearGradient id="fg2" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="rg2" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="date" tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis domain={[0.6, 1.0]} tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
            <Tooltip formatter={(v: number) => `${(v * 100).toFixed(1)}%`} />
            <Area type="monotone" dataKey="faithfulness" name="Faithfulness" stroke="#10b981" strokeWidth={2} fill="url(#fg2)" />
            <Area type="monotone" dataKey="recall" name="Recall@5" stroke="#06b6d4" strokeWidth={2} fill="url(#rg2)" />
          </AreaChart>
        </ResponsiveContainer>
      </motion.div>

      {/* Benchmark breakdown */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.3 }}
        className="grid grid-cols-2 gap-4"
      >
        {/* Golden QA */}
        <div className="glass rounded-2xl p-5">
          <p className="font-semibold text-white text-sm mb-4">Golden QA Dataset (40 questions)</p>
          <div className="space-y-3">
            {[
              { label: "Chunking failures", count: 8, total: 40, color: "amber" as const },
              { label: "Retrieval misses", count: 12, total: 40, color: "cyan" as const },
              { label: "Reranker failures", count: 7, total: 40, color: "violet" as const },
              { label: "Generation failures", count: 6, total: 40, color: "emerald" as const },
              { label: "Correct (no failure)", count: 7, total: 40, color: "emerald" as const },
            ].map(({ label, count, total, color }) => (
              <div key={label}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-400">{label}</span>
                  <span className="text-slate-300">{count}/{total}</span>
                </div>
                <Progress value={count} max={total} color={color} />
              </div>
            ))}
          </div>
        </div>

        {/* Corruption benchmark */}
        <div className="glass rounded-2xl p-5">
          <p className="font-semibold text-white text-sm mb-4">Corruption Benchmark (60 cases)</p>
          <div className="space-y-3">
            {[
              { label: "Retrieval corruptions", count: 20, total: 60, accuracy: 0.80, color: "cyan" as const },
              { label: "Chunking corruptions", count: 15, total: 60, accuracy: 0.73, color: "amber" as const },
              { label: "Reranker corruptions", count: 15, total: 60, accuracy: 0.67, color: "violet" as const },
              { label: "Generation corruptions", count: 10, total: 60, accuracy: 0.70, color: "emerald" as const },
            ].map(({ label, count, total, accuracy, color }) => (
              <div key={label}>
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-slate-400">{label} ({count} cases)</span>
                  <span className={cn("font-medium", accuracy >= 0.70 ? "text-emerald-400" : "text-amber-400")}>
                    {(accuracy * 100).toFixed(0)}% acc.
                  </span>
                </div>
                <Progress value={accuracy} color={color} />
              </div>
            ))}
          </div>
          <div className="mt-4 pt-4 border-t border-white/[0.06] flex items-center justify-between">
            <span className="text-xs text-slate-500">Overall accuracy</span>
            <div className="flex items-center gap-2">
              <span className="text-lg font-black text-emerald-400">73.3%</span>
              <Badge variant="success">≥0.70 threshold ✓</Badge>
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
