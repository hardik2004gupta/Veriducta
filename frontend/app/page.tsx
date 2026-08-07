"use client";

import Link from "next/link";
import { motion } from "framer-motion";
import { ArrowRight, Github, BookOpen, Zap, Shield, Brain, Search, GitBranch, BarChart3, CheckCircle2, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

// ── Animation variants ────────────────────────────────────────────────────────

const fadeUp = {
  hidden: { opacity: 0, y: 32 },
  visible: (delay = 0) => ({
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: [0.25, 0.46, 0.45, 0.94], delay },
  }),
};

// ── Pipeline diagram component ────────────────────────────────────────────────

const STAGES = [
  { label: "Chunking", color: "amber", desc: "Boundary-aware hierarchical splits", icon: "C" },
  { label: "Retrieval", color: "cyan", desc: "BM25 + dense + RRF + temporal filter", icon: "R" },
  { label: "Reranking", color: "violet", desc: "Cross-encoder reorder", icon: "X" },
  { label: "Generation", color: "emerald", desc: "Claude Sonnet 4.6 structured output", icon: "G" },
];

const colorMap: Record<string, string> = {
  amber: "from-amber-500/30 to-amber-600/20 border-amber-500/30 shadow-amber-500/10",
  cyan: "from-cyan-500/30 to-cyan-600/20 border-cyan-500/30 shadow-cyan-500/10",
  violet: "from-violet-500/30 to-violet-600/20 border-violet-500/30 shadow-violet-500/10",
  emerald: "from-emerald-500/30 to-emerald-600/20 border-emerald-500/30 shadow-emerald-500/10",
};

const textMap: Record<string, string> = {
  amber: "text-amber-300",
  cyan: "text-cyan-300",
  violet: "text-violet-300",
  emerald: "text-emerald-300",
};

function PipelineDiagram() {
  return (
    <div className="relative flex items-center gap-3">
      {STAGES.map((stage, i) => (
        <div key={stage.label} className="flex items-center gap-3">
          <motion.div
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.5 + i * 0.15, duration: 0.5, ease: "backOut" }}
            className={`relative rounded-2xl bg-gradient-to-br border px-4 py-5 shadow-xl ${colorMap[stage.color]}`}
          >
            <div className={`mb-1 text-xl font-black ${textMap[stage.color]}`}>{stage.icon}</div>
            <div className={`text-sm font-semibold ${textMap[stage.color]}`}>{stage.label}</div>
            <div className="mt-1 text-[10px] text-slate-500 leading-tight max-w-[90px]">{stage.desc}</div>
          </motion.div>
          {i < STAGES.length - 1 && (
            <motion.div
              initial={{ opacity: 0, scaleX: 0 }}
              animate={{ opacity: 1, scaleX: 1 }}
              transition={{ delay: 0.7 + i * 0.15, duration: 0.4 }}
              className="flex items-center gap-1"
            >
              <div className="h-px w-8 bg-gradient-to-r from-white/20 to-white/10" />
              <div className="h-1.5 w-1.5 rounded-full bg-white/30" />
            </motion.div>
          )}
        </div>
      ))}

      {/* Attribution arrow */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 1.5, duration: 0.8 }}
        className="absolute -bottom-10 left-0 right-0 flex items-center justify-center"
      >
        <div className="flex items-center gap-2 rounded-full bg-red-500/10 border border-red-500/20 px-4 py-1.5">
          <div className="h-2 w-2 rounded-full bg-red-400 animate-pulse" />
          <span className="text-xs text-red-300 font-medium">Root cause: Retrieval (−0.31 quality delta)</span>
        </div>
      </motion.div>
    </div>
  );
}

// ── Feature cards ─────────────────────────────────────────────────────────────

const FEATURES = [
  {
    icon: Search,
    color: "cyan",
    title: "Traceable Hybrid Retrieval",
    desc: "Every BM25 score, dense score, RRF rank, and temporal filter decision is stored. No inference needed to replay.",
  },
  {
    icon: GitBranch,
    color: "violet",
    title: "Four-Stage Causal Ablation",
    desc: "Swap gold chunks at each stage and measure quality delta. Isolates whether chunking, retrieval, reranking, or generation failed.",
  },
  {
    icon: Shield,
    color: "emerald",
    title: "Claim-Level NLI Verification",
    desc: "Every claim is verified against its cited chunk with cross-encoder NLI. Contradictions and ambiguities are flagged automatically.",
  },
  {
    icon: Brain,
    color: "amber",
    title: "4 Metrics RAGAS Can't Compute",
    desc: "Omission rate, causal attribution accuracy, temporal-valid retrieval rate, contradiction acknowledgment rate.",
  },
  {
    icon: BarChart3,
    color: "cyan",
    title: "CI Regression Gate",
    desc: "Five blocking conditions gate every merge. Faithfulness drop >2%, Recall@5 drop >3%, p95 latency >20% - all auto-blocked.",
  },
  {
    icon: Zap,
    color: "violet",
    title: "O(1) Evidence Log Lookup",
    desc: "SQLite-indexed JSONL evidence log. Seek to byte offset for instant trace retrieval without full-file scans.",
  },
];

const featureColorMap: Record<string, { icon: string; glow: string }> = {
  cyan: { icon: "text-cyan-400", glow: "hover:shadow-cyan-500/10 hover:border-cyan-500/20" },
  violet: { icon: "text-violet-400", glow: "hover:shadow-violet-500/10 hover:border-violet-500/20" },
  emerald: { icon: "text-emerald-400", glow: "hover:shadow-emerald-500/10 hover:border-emerald-500/20" },
  amber: { icon: "text-amber-400", glow: "hover:shadow-amber-500/10 hover:border-amber-500/20" },
};

// ── Benchmark numbers ─────────────────────────────────────────────────────────

const BENCHMARKS = [
  { value: "0.73+", label: "Root-Cause Accuracy", sub: "on 60-case benchmark" },
  { value: "0.87+", label: "Citation Faithfulness", sub: "NLI entailment verified" },
  { value: "0.78+", label: "Recall@5", sub: "on 40-question golden QA" },
  { value: "<4s", label: "p50 Latency", sub: "end-to-end query" },
];

// ── Tech stack ────────────────────────────────────────────────────────────────

const TECH = [
  ["Claude Sonnet 4.6", "LLM"],
  ["BGE-large-en-v1.5", "Embedding"],
  ["nli-deberta-v3-base", "NLI"],
  ["ms-marco-MiniLM-L-12-v2", "Reranker"],
  ["Qdrant", "Vector DB"],
  ["FastAPI", "API"],
  ["Next.js 15", "Frontend"],
  ["Prometheus", "Metrics"],
  ["OpenTelemetry", "Tracing"],
  ["RAGAS", "Baseline"],
];

// ── Main page ─────────────────────────────────────────────────────────────────

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-background grid-bg text-white overflow-x-hidden">
      {/* Ambient glows */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute left-1/2 top-0 h-[600px] w-[600px] -translate-x-1/2 rounded-full bg-cyan-500/8 blur-[120px]" />
        <div className="absolute left-1/4 bottom-1/3 h-64 w-64 rounded-full bg-violet-500/8 blur-3xl" />
        <div className="absolute right-1/4 top-1/3 h-64 w-64 rounded-full bg-emerald-500/6 blur-3xl" />
      </div>

      {/* Navbar */}
      <nav className="relative z-10 flex items-center justify-between px-8 py-5 border-b border-white/[0.06] backdrop-blur-xl">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-teal-600">
            <Zap className="h-4 w-4 text-white" />
          </div>
          <span className="font-bold text-white tracking-tight">Veriducta</span>
          <Badge variant="muted">v1.0.0</Badge>
        </div>
        <div className="flex items-center gap-4">
          <Link href="/docs" className="text-sm text-slate-400 hover:text-white transition-colors">Docs</Link>
          <a href="https://github.com/hardik2004gupta/Veriducta" target="_blank" rel="noopener noreferrer" className="text-sm text-slate-400 hover:text-white transition-colors flex items-center gap-1.5">
            <Github className="h-4 w-4" /> GitHub
          </a>
          <Link href="/dashboard">
            <Button size="sm">Open Dashboard <ArrowRight className="h-3.5 w-3.5" /></Button>
          </Link>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="relative z-10 px-8 pt-24 pb-32 text-center max-w-6xl mx-auto">
        <motion.div
          initial="hidden"
          animate="visible"
          variants={fadeUp}
          custom={0}
          className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-1.5 mb-8"
        >
          <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-xs text-slate-300 font-medium">
            Root-cause every failed RAG answer · Four-stage causal ablation
          </span>
        </motion.div>

        <motion.h1
          initial="hidden"
          animate="visible"
          variants={fadeUp}
          custom={0.1}
          className="text-6xl font-black leading-[1.05] tracking-tight mb-6"
        >
          When your RAG pipeline fails,
          <br />
          <span className="gradient-text">know exactly why.</span>
        </motion.h1>

        <motion.p
          initial="hidden"
          animate="visible"
          variants={fadeUp}
          custom={0.2}
          className="mx-auto max-w-2xl text-lg text-slate-400 leading-relaxed mb-10"
        >
          Veriducta stores a complete, replayable trace of every retrieval decision and
          runs four-stage causal ablation to attribute answer degradation to a specific pipeline
          stage - chunking, retrieval, reranking, or generation - without re-running expensive inference.
        </motion.p>

        <motion.div
          initial="hidden"
          animate="visible"
          variants={fadeUp}
          custom={0.3}
          className="flex items-center justify-center gap-4 mb-20"
        >
          <Link href="/dashboard">
            <Button size="lg">
              Open Dashboard <ArrowRight className="h-4 w-4" />
            </Button>
          </Link>
          <Link href="/ask">
            <Button size="lg" variant="outline">
              Try a Query
            </Button>
          </Link>
          <a href="https://github.com/hardik2004gupta/Veriducta" target="_blank" rel="noopener noreferrer">
            <Button size="lg" variant="ghost">
              <Github className="h-4 w-4" /> GitHub
            </Button>
          </a>
        </motion.div>

        {/* Pipeline Diagram */}
        <motion.div
          initial={{ opacity: 0, y: 40 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4, duration: 0.7 }}
          className="relative"
        >
          <div className="glass rounded-3xl p-10 inline-block">
            <p className="text-xs text-slate-500 uppercase tracking-widest mb-6">RAG Pipeline with Causal Tracing</p>
            <PipelineDiagram />
          </div>
        </motion.div>
      </section>

      {/* ── Benchmarks ── */}
      <section className="relative z-10 px-8 py-20 border-y border-white/[0.06]">
        <div className="mx-auto max-w-5xl grid grid-cols-2 gap-6 md:grid-cols-4">
          {BENCHMARKS.map((b, i) => (
            <motion.div
              key={b.label}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.08, duration: 0.5 }}
              className="text-center"
            >
              <div className="gradient-text text-5xl font-black tabular-nums">{b.value}</div>
              <div className="mt-2 font-semibold text-white">{b.label}</div>
              <div className="text-xs text-slate-500 mt-1">{b.sub}</div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ── Problem ── */}
      <section className="relative z-10 px-8 py-24 max-w-5xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <Badge variant="warning" className="mb-4">The Problem</Badge>
          <h2 className="text-4xl font-black text-white mb-4">
            Standard RAG tooling can&apos;t tell you why.
          </h2>
          <p className="max-w-2xl mx-auto text-slate-400">
            RAGAS faithfulness scores a bad answer at 0.82. But was it a chunking split that cut a critical clause?
            A retrieval miss on the gold chunk? A reranker that buried the right evidence? Or a generation hallucination?
            RAGAS cannot tell you. Veriducta can.
          </p>
        </motion.div>

        {/* Comparison table */}
        <div className="glass rounded-2xl overflow-hidden">
          <div className="grid grid-cols-3 text-sm">
            <div className="p-4 border-b border-white/10 text-slate-500 font-medium">Capability</div>
            <div className="p-4 border-b border-white/10 text-slate-400 font-medium text-center">RAGAS</div>
            <div className="p-4 border-b border-white/10 text-cyan-300 font-semibold text-center">Veriducta</div>

            {[
              ["Faithfulness scoring", true, true],
              ["Recall@K", true, true],
              ["Omission rate", false, true],
              ["Causal root-cause attribution", false, true],
              ["Temporal-valid retrieval rate", false, true],
              ["Contradiction acknowledgment rate", false, true],
              ["Replayable retrieval traces", false, true],
              ["Stage-level quality delta", false, true],
            ].map(([cap, ragas, ours], i) => (
              <div key={String(cap)} className="contents">
                <div className={`px-4 py-3 text-slate-300 ${i % 2 === 0 ? "bg-white/[0.01]" : ""}`}>{String(cap)}</div>
                <div className={`px-4 py-3 text-center ${i % 2 === 0 ? "bg-white/[0.01]" : ""}`}>
                  {ragas ? <CheckCircle2 className="h-4 w-4 text-slate-500 mx-auto" /> : <span className="text-slate-700">-</span>}
                </div>
                <div className={`px-4 py-3 text-center ${i % 2 === 0 ? "bg-white/[0.01]" : ""}`}>
                  <CheckCircle2 className="h-4 w-4 text-emerald-400 mx-auto" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="relative z-10 px-8 py-24 max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <Badge variant="default" className="mb-4">Features</Badge>
          <h2 className="text-4xl font-black text-white">
            Engineered for causal certainty.
          </h2>
        </motion.div>

        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => {
            const colors = featureColorMap[f.color];
            return (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.07 }}
                className={`glass rounded-2xl p-6 border border-transparent transition-all duration-300 hover:shadow-xl ${colors.glow}`}
              >
                <div className={`mb-4 ${colors.icon}`}>
                  <f.icon className="h-6 w-6" />
                </div>
                <h3 className="font-semibold text-white mb-2">{f.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
              </motion.div>
            );
          })}
        </div>
      </section>

      {/* ── Architecture section ── */}
      <section className="relative z-10 px-8 py-24 border-t border-white/[0.06] max-w-5xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <Badge variant="default" className="mb-4">Architecture</Badge>
          <h2 className="text-4xl font-black text-white mb-4">Eight-layer observability stack.</h2>
          <p className="text-slate-400 max-w-xl mx-auto">
            Each layer has explicit dependency rules. Retrieval cannot call FastAPI. Replay cannot re-ingest documents.
            No circular imports. No business logic in route handlers.
          </p>
        </motion.div>

        <div className="glass rounded-2xl p-8">
          <div className="space-y-2 font-mono text-sm">
            {[
              { label: "API Layer", sub: "FastAPI · routing · DI · exception mapping", color: "text-slate-400" },
              { label: "Evaluation", sub: "40 gold QA · 60 corruptions · regression gate · RAGAS baseline", color: "text-amber-300" },
              { label: "Causal Replay", sub: "Stage 1–4 ablation · quality delta · root-cause attribution", color: "text-violet-300" },
              { label: "Verification", sub: "NLI claim checking · counterevidence scan · expert flagging", color: "text-emerald-300" },
              { label: "Generation", sub: "Claude Sonnet 4.6 · JSON schema enforcement · token logging", color: "text-cyan-300" },
              { label: "Retrieval", sub: "BM25 + dense · RRF · temporal filter · cross-encoder · expander", color: "text-cyan-300" },
              { label: "Ingestion", sub: "PyMuPDF · hierarchical chunking · BGE embeddings · Qdrant upsert", color: "text-slate-300" },
              { label: "Foundation", sub: "config · core · schemas · utils · observability · storage · models", color: "text-slate-500" },
            ].map((layer, i) => (
              <div key={layer.label} className="flex items-center gap-4 rounded-xl px-4 py-3 bg-white/[0.02] border border-white/[0.04]">
                <span className="text-slate-600 w-4 shrink-0">{i + 1}</span>
                <span className={`font-semibold w-36 shrink-0 ${layer.color}`}>{layer.label}</span>
                <span className="text-slate-500 text-xs">{layer.sub}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Tech stack ── */}
      <section className="relative z-10 px-8 py-20 border-t border-white/[0.06]">
        <div className="max-w-5xl mx-auto">
          <div className="text-center mb-12">
            <h2 className="text-2xl font-bold text-white">Technology Stack</h2>
          </div>
          <div className="flex flex-wrap justify-center gap-3">
            {TECH.map(([name, role]) => (
              <div
                key={name}
                className="glass rounded-xl px-4 py-2.5 flex items-center gap-2"
              >
                <span className="text-sm font-medium text-white">{name}</span>
                <span className="text-[10px] text-slate-500 uppercase tracking-wider">{role}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="relative z-10 px-8 py-32 text-center">
        <div className="max-w-3xl mx-auto">
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            whileInView={{ opacity: 1, scale: 1 }}
            viewport={{ once: true }}
            className="glass rounded-3xl p-16 relative overflow-hidden"
          >
            <div className="absolute inset-0 bg-gradient-to-br from-cyan-500/5 to-violet-500/5" />
            <div className="relative z-10">
              <h2 className="text-4xl font-black text-white mb-4">
                Ready to attribute your first failure?
              </h2>
              <p className="text-slate-400 mb-8 max-w-xl mx-auto">
                Open the dashboard, run a query, and see which stage caused degradation -
                down to a quality delta and a named chunk ID.
              </p>
              <div className="flex items-center justify-center gap-4">
                <Link href="/dashboard">
                  <Button size="lg">
                    Open Dashboard <ArrowRight className="h-4 w-4" />
                  </Button>
                </Link>
                <Link href="/docs">
                  <Button size="lg" variant="outline">
                    <BookOpen className="h-4 w-4" /> Read the Docs
                  </Button>
                </Link>
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-white/[0.06] px-8 py-8 text-center">
        <div className="flex items-center justify-center gap-4 text-sm text-slate-600">
          <span>Built with precision by Hardik Gupta</span>
          <span>·</span>
          <a href="https://github.com/hardik2004gupta/Veriducta" target="_blank" rel="noopener noreferrer" className="hover:text-slate-400 transition-colors flex items-center gap-1">
            GitHub <ExternalLink className="h-3 w-3" />
          </a>
          <span>·</span>
          <span>MIT License</span>
        </div>
      </footer>
    </div>
  );
}
