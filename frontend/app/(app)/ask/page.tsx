"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Send, Loader2, FileText, Shield, Zap, Clock, AlertTriangle, CheckCircle2, ChevronDown, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { MOCK_ANSWER, MOCK_RETRIEVAL_TRACE } from "@/lib/mock-data";
import type { Claim } from "@/types";

// ── Example queries ───────────────────────────────────────────────────────────

const EXAMPLE_QUERIES = [
  "What are the OSHA permissible exposure limits for respirable crystalline silica?",
  "How does NIST define uncertainty in measurement traceability?",
  "What geotechnical criteria apply to seismic site classification?",
  "Describe the requirements for confined space entry permits under OSHA 1910.146.",
  "What are the temporal validity rules for USGS hazard map supersession?",
];

// ── Streaming dot animation ───────────────────────────────────────────────────

function TypingDots() {
  return (
    <div className="flex items-center gap-1">
      {[0, 0.2, 0.4].map((delay, i) => (
        <motion.div
          key={i}
          className="h-1.5 w-1.5 rounded-full bg-cyan-400"
          animate={{ opacity: [0.3, 1, 0.3] }}
          transition={{ repeat: Infinity, duration: 1.2, delay }}
        />
      ))}
    </div>
  );
}

// ── Claim card ────────────────────────────────────────────────────────────────

function ClaimCard({ claim, index }: { claim: Claim; index: number }) {
  const [open, setOpen] = useState(false);

  const status = claim.verification_status;
  const statusStyles: Record<string, { badge: "success" | "danger" | "warning" | "muted"; label: string; icon: React.ElementType }> = {
    supported: { badge: "success", label: "Supported", icon: CheckCircle2 },
    contradicted: { badge: "danger", label: "Contradicted", icon: AlertTriangle },
    ambiguous_conditional: { badge: "warning", label: "Ambiguous", icon: AlertTriangle },
    not_searched: { badge: "muted", label: "Not searched", icon: Shield },
    unresolved: { badge: "muted", label: "Unresolved", icon: Shield },
  };
  const s = statusStyles[status] ?? statusStyles.unresolved;
  const StatusIcon = s.icon;

  const entailProb = claim.nli_entailment_probability ?? 0;
  const contradictProb = claim.nli_contradiction_probability ?? 0;
  const neutralProb = claim.nli_neutral_probability ?? 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.1 }}
      className="glass rounded-xl overflow-hidden"
    >
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-start gap-3 p-4 text-left hover:bg-white/[0.02] transition-colors"
      >
        <span className="text-xs text-slate-500 mt-0.5 w-5 shrink-0">C{index + 1}</span>
        <span className="flex-1 text-sm text-slate-200 leading-relaxed">{claim.text}</span>
        <div className="flex items-center gap-2 shrink-0">
          <Badge variant={s.badge}>
            <StatusIcon className="h-3 w-3" />
            {s.label}
          </Badge>
          {open ? <ChevronDown className="h-4 w-4 text-slate-500" /> : <ChevronRight className="h-4 w-4 text-slate-500" />}
        </div>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <div className="border-t border-white/[0.06] px-4 py-4 space-y-4">
              {/* NLI probabilities */}
              <div className="space-y-2">
                <p className="text-xs text-slate-500 uppercase tracking-wider">NLI Probabilities</p>
                <div className="grid grid-cols-3 gap-3">
                  {[
                    { label: "Entailment", value: entailProb, color: "emerald" as const },
                    { label: "Contradiction", value: contradictProb, color: "red" as const },
                    { label: "Neutral", value: neutralProb, color: "amber" as const },
                  ].map(({ label, value, color }) => (
                    <div key={label}>
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-slate-500">{label}</span>
                        <span className="text-white font-medium">{(value * 100).toFixed(1)}%</span>
                      </div>
                      <Progress value={value} color={color} />
                    </div>
                  ))}
                </div>
              </div>

              {/* Cited chunk */}
              <div>
                <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Cited Chunk</p>
                <div className="rounded-lg bg-white/[0.03] border border-white/[0.06] px-3 py-2">
                  <div className="flex items-center gap-2 mb-1">
                    <FileText className="h-3.5 w-3.5 text-slate-500" />
                    <code className="text-xs text-cyan-300">{claim.citation_chunk_id}</code>
                  </div>
                  <p className="text-xs text-slate-400 leading-relaxed line-clamp-3">
                    {claim.excerpt ?? "Excerpt not available in this context."}
                  </p>
                </div>
              </div>

              {/* Key entities */}
              {claim.key_entities.length > 0 && (
                <div>
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-2">Key Entities</p>
                  <div className="flex flex-wrap gap-1.5">
                    {claim.key_entities.map((e) => (
                      <span key={e} className="rounded-md bg-white/5 border border-white/[0.08] px-2 py-0.5 text-xs text-slate-300">
                        {e}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {claim.requires_expert_review && (
                <div className="flex items-center gap-2 rounded-lg bg-amber-500/10 border border-amber-500/20 px-3 py-2">
                  <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0" />
                  <p className="text-xs text-amber-300">Flagged for expert review - contradiction or ambiguity detected.</p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ── Evidence panel ────────────────────────────────────────────────────────────

function EvidencePanel({ traceId }: { traceId: string }) {
  const trace = MOCK_RETRIEVAL_TRACE;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500 uppercase tracking-wider">Retrieval Trace</p>
        <code className="text-xs text-cyan-300">{traceId.slice(0, 16)}…</code>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="glass rounded-xl p-3 text-center">
          <p className="text-xl font-black text-cyan-400">{trace.bm25_candidates}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">BM25 candidates</p>
        </div>
        <div className="glass rounded-xl p-3 text-center">
          <p className="text-xl font-black text-violet-400">{trace.dense_candidates}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">dense candidates</p>
        </div>
        <div className="glass rounded-xl p-3 text-center">
          <p className="text-xl font-black text-emerald-400">{trace.after_rerank}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">after rerank</p>
        </div>
        <div className="glass rounded-xl p-3 text-center">
          <p className="text-xl font-black text-red-400">{trace.temporal_rejections.length}</p>
          <p className="text-[10px] text-slate-500 mt-0.5">temporal rejects</p>
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-xs text-slate-500 uppercase tracking-wider">Top Retrieved</p>
        {trace.candidates.slice(0, 3).map((c, i) => (
          <div key={c.chunk_id} className="glass rounded-xl p-3">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] text-slate-500">#{i + 1}</span>
              <code className="text-[10px] text-cyan-300">{c.chunk_id}</code>
            </div>
            <p className="text-xs text-slate-300 line-clamp-2 leading-relaxed">{c.text_excerpt}</p>
            <div className="flex items-center gap-3 mt-2">
              <div className="flex items-center gap-1">
                <div className="h-1.5 w-1.5 rounded-full bg-cyan-400" />
                <span className="text-[10px] text-slate-500">BM25 {c.bm25_score?.toFixed(3) ?? "-"}</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="h-1.5 w-1.5 rounded-full bg-violet-400" />
                <span className="text-[10px] text-slate-500">dense {c.dense_score?.toFixed(3) ?? "-"}</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                <span className="text-[10px] text-slate-500">RRF {c.rrf_score?.toFixed(4) ?? "-"}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

interface Message {
  role: "user" | "assistant";
  content: string;
  answer?: typeof MOCK_ANSWER;
  traceId?: string;
}

export default function AskPage() {
  const [query, setQuery] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"claims" | "evidence" | "trace">("claims");
  const [activeMsg, setActiveMsg] = useState<Message | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function autoResize() {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }

  async function handleSubmit() {
    const q = query.trim();
    if (!q || loading) return;
    setQuery("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";

    const userMsg: Message = { role: "user", content: q };
    setMessages((prev) => [...prev, userMsg]);
    setLoading(true);

    // Simulate pipeline latency
    await new Promise((r) => setTimeout(r, 2200));

    const traceId = crypto.randomUUID();
    const assistantMsg: Message = {
      role: "assistant",
      content: MOCK_ANSWER.summary,
      answer: MOCK_ANSWER,
      traceId,
    };
    setMessages((prev) => [...prev, assistantMsg]);
    setActiveMsg(assistantMsg);
    setLoading(false);
  }

  function handleKey(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  const showPanel = activeMsg !== null;

  return (
    <div className="flex h-[calc(100vh-4rem)] gap-4 -m-8">
      {/* Chat column */}
      <div className={cn("flex flex-col min-w-0 transition-all duration-300", showPanel ? "w-[55%]" : "w-full")}>
        {/* Header */}
        <div className="flex items-center justify-between px-8 py-5 border-b border-white/[0.06]">
          <div>
            <h1 className="text-lg font-black text-white">Ask Veriducta</h1>
            <p className="text-xs text-slate-500">Claim-verified answers over your corpus</p>
          </div>
          <div className="flex items-center gap-2 glass rounded-xl px-3 py-2">
            <Zap className="h-3.5 w-3.5 text-cyan-400" />
            <span className="text-xs text-slate-400">claude-sonnet-4-6</span>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto scrollbar-thin px-8 py-6 space-y-6">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-gradient-to-br from-cyan-500/20 to-teal-500/10 border border-cyan-500/20 mb-4">
                <Zap className="h-8 w-8 text-cyan-400" />
              </div>
              <h2 className="text-lg font-bold text-white mb-2">Ask anything about your corpus</h2>
              <p className="text-sm text-slate-500 mb-8 max-w-md">
                Every answer is claim-verified with NLI entailment. All retrieval decisions are traced.
              </p>
              <div className="grid gap-2 w-full max-w-lg">
                {EXAMPLE_QUERIES.slice(0, 3).map((q) => (
                  <button
                    key={q}
                    onClick={() => { setQuery(q); textareaRef.current?.focus(); }}
                    className="glass rounded-xl px-4 py-3 text-sm text-slate-300 text-left hover:bg-white/[0.05] hover:text-white transition-colors border border-white/[0.06] hover:border-white/[0.12]"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <motion.div
              key={i}
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35 }}
            >
              {msg.role === "user" ? (
                <div className="flex justify-end">
                  <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-gradient-to-br from-cyan-500/20 to-teal-500/10 border border-cyan-500/20 px-4 py-3 text-sm text-slate-200">
                    {msg.content}
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="flex items-start gap-3">
                    <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-teal-600 shadow-lg shadow-cyan-500/20">
                      <Zap className="h-3.5 w-3.5 text-white" />
                    </div>
                    <div className="flex-1">
                      <div className="glass rounded-2xl rounded-tl-sm px-4 py-3">
                        <p className="text-sm text-slate-200 leading-relaxed">{msg.content}</p>
                      </div>
                      {msg.answer && (
                        <div className="mt-2 flex items-center gap-3 text-xs text-slate-500">
                          <div className="flex items-center gap-1">
                            <Clock className="h-3.5 w-3.5" />
                            {msg.answer.latency_ms}ms
                          </div>
                          <div className="flex items-center gap-1">
                            <Shield className="h-3.5 w-3.5" />
                            {msg.answer.claims.length} claims verified
                          </div>
                          <button
                            onClick={() => setActiveMsg(msg)}
                            className="flex items-center gap-1 text-cyan-400 hover:text-cyan-300 transition-colors"
                          >
                            View evidence <ChevronRight className="h-3 w-3" />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </motion.div>
          ))}

          {loading && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-start gap-3">
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-teal-600">
                <Loader2 className="h-3.5 w-3.5 text-white animate-spin" />
              </div>
              <div className="glass rounded-2xl rounded-tl-sm px-4 py-3">
                <div className="flex items-center gap-3 text-xs text-slate-500">
                  <TypingDots />
                  <span>Running pipeline · BM25 + dense retrieval · reranking · generating…</span>
                </div>
              </div>
            </motion.div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="px-8 py-5 border-t border-white/[0.06]">
          <div className="glass rounded-2xl overflow-hidden border border-white/[0.08] focus-within:border-cyan-500/30 transition-colors">
            <textarea
              ref={textareaRef}
              value={query}
              onChange={(e) => { setQuery(e.target.value); autoResize(); }}
              onKeyDown={handleKey}
              placeholder="Ask anything about your corpus… (Enter to send)"
              rows={1}
              className="w-full bg-transparent px-4 pt-4 pb-2 text-sm text-white placeholder-slate-600 resize-none focus:outline-none scrollbar-thin"
              style={{ minHeight: 52 }}
            />
            <div className="flex items-center justify-between px-4 pb-3">
              <div className="flex items-center gap-2 text-xs text-slate-600">
                <span>⏎ send · ⇧⏎ newline</span>
              </div>
              <Button size="sm" onClick={handleSubmit} disabled={!query.trim() || loading}>
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                Send
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Evidence panel */}
      <AnimatePresence>
        {showPanel && activeMsg?.answer && (
          <motion.div
            key="panel"
            initial={{ opacity: 0, x: 32 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 32 }}
            transition={{ duration: 0.3 }}
            className="w-[45%] border-l border-white/[0.06] flex flex-col"
          >
            {/* Panel header */}
            <div className="flex items-center justify-between px-6 py-5 border-b border-white/[0.06]">
              <div className="flex gap-1 glass rounded-xl p-1">
                {(["claims", "evidence", "trace"] as const).map((tab) => (
                  <button
                    key={tab}
                    onClick={() => setActiveTab(tab)}
                    className={cn(
                      "px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all",
                      activeTab === tab ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/20" : "text-slate-500 hover:text-slate-300",
                    )}
                  >
                    {tab}
                  </button>
                ))}
              </div>
              <button onClick={() => setActiveMsg(null)} className="text-slate-600 hover:text-slate-400 text-xs">
                ✕ Close
              </button>
            </div>

            {/* Panel body */}
            <div className="flex-1 overflow-y-auto scrollbar-thin px-6 py-5">
              {activeTab === "claims" && (
                <div className="space-y-3">
                  <p className="text-xs text-slate-500 uppercase tracking-wider mb-4">
                    {activeMsg.answer.claims.length} Verified Claims
                  </p>
                  {activeMsg.answer.claims.map((c, i) => (
                    <ClaimCard key={c.claim_id} claim={c} index={i} />
                  ))}
                </div>
              )}

              {activeTab === "evidence" && activeMsg.traceId && (
                <EvidencePanel traceId={activeMsg.traceId} />
              )}

              {activeTab === "trace" && (
                <div className="space-y-4">
                  <p className="text-xs text-slate-500 uppercase tracking-wider">Generation Trace</p>
                  <div className="glass rounded-2xl p-4 space-y-3">
                    {[
                      { label: "Model", value: activeMsg.answer.model },
                      { label: "Input tokens", value: activeMsg.answer.input_tokens.toLocaleString() },
                      { label: "Output tokens", value: activeMsg.answer.output_tokens.toLocaleString() },
                      { label: "Est. cost", value: `$${activeMsg.answer.cost_usd.toFixed(5)}` },
                      { label: "Latency", value: `${activeMsg.answer.latency_ms}ms` },
                      { label: "Schema attempts", value: activeMsg.answer.schema_validation_attempts },
                      { label: "Config hash", value: activeMsg.answer.config_snapshot_hash.slice(0, 12) + "…" },
                    ].map(({ label, value }) => (
                      <div key={label} className="flex justify-between text-sm">
                        <span className="text-slate-500">{label}</span>
                        <span className="text-slate-200 font-mono text-xs">{String(value)}</span>
                      </div>
                    ))}
                  </div>

                  <p className="text-xs text-slate-500 uppercase tracking-wider">Confidence</p>
                  <div className="glass rounded-2xl px-4 py-3">
                    <p className="text-3xl font-black gradient-text">{activeMsg.answer.confidence_tag.toUpperCase()}</p>
                    <p className="text-xs text-slate-500 mt-1">
                      {activeMsg.answer.requires_expert_review ? "Expert review required" : "No expert review required"}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
