"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Settings, Brain, Database, Sliders, Shield, Save, CheckCircle2, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// ── Setting row ───────────────────────────────────────────────────────────────

function SettingRow({
  label,
  description,
  children,
}: {
  label: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex items-start justify-between gap-8 py-4 border-b border-white/[0.04] last:border-0">
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-white">{label}</p>
        <p className="text-xs text-slate-500 mt-0.5 leading-relaxed">{description}</p>
      </div>
      <div className="shrink-0">{children}</div>
    </div>
  );
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={cn(
        "relative h-6 w-11 rounded-full transition-colors duration-200",
        checked ? "bg-cyan-500" : "bg-white/20",
      )}
    >
      <div
        className={cn(
          "absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform duration-200",
          checked ? "translate-x-5" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

function NumberInput({
  value,
  onChange,
  min,
  max,
  step = 1,
}: {
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step?: number;
}) {
  return (
    <input
      type="number"
      value={value}
      min={min}
      max={max}
      step={step}
      onChange={(e) => onChange(Number(e.target.value))}
      className="w-24 bg-white/5 border border-white/[0.08] rounded-lg px-3 py-1.5 text-sm text-white text-right focus:outline-none focus:border-cyan-500/40 tabular-nums"
    />
  );
}

function SelectInput({ value, onChange, options }: {
  value: string;
  onChange: (v: string) => void;
  options: string[];
}) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-white/5 border border-white/[0.08] rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-cyan-500/40"
    >
      {options.map((o) => (
        <option key={o} value={o} className="bg-[#0a0f1a]">{o}</option>
      ))}
    </select>
  );
}

// ── Sections ──────────────────────────────────────────────────────────────────

const SECTIONS = [
  { id: "models", label: "Models", icon: Brain },
  { id: "retrieval", label: "Retrieval", icon: Database },
  { id: "thresholds", label: "NLI Thresholds", icon: Sliders },
  { id: "security", label: "Security", icon: Shield },
] as const;

type Section = typeof SECTIONS[number]["id"];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function SettingsPage() {
  const [activeSection, setActiveSection] = useState<Section>("models");
  const [saved, setSaved] = useState(false);

  // Model settings
  const [llmModel, setLlmModel] = useState("claude-sonnet-4-6");
  const [maxTokens, setMaxTokens] = useState(2048);
  const [schemaRetries, setSchemaRetries] = useState(2);
  const [embeddingModel, setEmbeddingModel] = useState("BAAI/bge-large-en-v1.5");

  // Retrieval settings
  const [bm25TopK, setBm25TopK] = useState(100);
  const [denseTopK, setDenseTopK] = useState(100);
  const [rrfK, setRrfK] = useState(60);
  const [rerankerTopInput, setRerankerTopInput] = useState(40);
  const [rerankerTopOutput, setRerankerTopOutput] = useState(8);
  const [embeddingCacheEnabled, setEmbeddingCacheEnabled] = useState(true);
  const [temporalFilterEnabled, setTemporalFilterEnabled] = useState(true);

  // NLI thresholds
  const [entailmentThreshold, setEntailmentThreshold] = useState(0.65);
  const [contradictionThreshold, setContradictionThreshold] = useState(0.85);
  const [neutralThreshold, setNeutralThreshold] = useState(0.40);

  // Security
  const [corsOrigins, setCorsOrigins] = useState("*");
  const [evidenceLogAccess, setEvidenceLogAccess] = useState(false);

  function handleSave() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  return (
    <div className="max-w-4xl space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black text-white">Settings</h1>
            <p className="text-sm text-slate-500 mt-1">Pipeline configuration · model parameters · NLI thresholds</p>
          </div>
          <div className="flex items-center gap-3">
            {saved && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex items-center gap-2 text-emerald-400 text-sm"
              >
                <CheckCircle2 className="h-4 w-4" /> Saved
              </motion.div>
            )}
            <Button onClick={handleSave}>
              <Save className="h-4 w-4" /> Save Changes
            </Button>
          </div>
        </div>
      </motion.div>

      <div className="flex gap-6">
        {/* Sidebar nav */}
        <div className="w-48 shrink-0">
          <nav className="space-y-1">
            {SECTIONS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveSection(id)}
                className={cn(
                  "w-full flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all",
                  activeSection === id
                    ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/20"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-200",
                )}
              >
                <Icon className={cn("h-4 w-4", activeSection === id ? "text-cyan-400" : "text-slate-500")} />
                {label}
              </button>
            ))}
          </nav>
        </div>

        {/* Setting panels */}
        <div className="flex-1">
          {activeSection === "models" && (
            <motion.div
              key="models"
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              className="glass rounded-2xl overflow-hidden"
            >
              <div className="px-6 py-4 border-b border-white/[0.06] flex items-center gap-2">
                <Brain className="h-4 w-4 text-violet-400" />
                <p className="font-semibold text-white text-sm">Model Configuration</p>
              </div>
              <div className="px-6">
                <SettingRow label="LLM Model" description="Claude model used for structured answer generation. Must support JSON output schema enforcement.">
                  <SelectInput value={llmModel} onChange={setLlmModel} options={["claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5-20251001"]} />
                </SettingRow>
                <SettingRow label="Max Tokens" description="Maximum output tokens per generation call. Recommended: 2048. Increasing this raises cost proportionally.">
                  <NumberInput value={maxTokens} onChange={setMaxTokens} min={512} max={8192} step={256} />
                </SettingRow>
                <SettingRow label="Schema Validation Retries" description="Number of retry attempts when the LLM response fails JSON schema validation. Each retry appends a correction instruction.">
                  <NumberInput value={schemaRetries} onChange={setSchemaRetries} min={0} max={5} />
                </SettingRow>
                <SettingRow label="Embedding Model" description="Dense embedding model for vector retrieval. Dimension is fixed at 1024. Changing this requires re-ingesting the entire corpus.">
                  <SelectInput value={embeddingModel} onChange={setEmbeddingModel} options={["BAAI/bge-large-en-v1.5"]} />
                </SettingRow>
                <div className="py-4">
                  <div className="flex items-start gap-2 rounded-xl bg-amber-500/5 border border-amber-500/10 px-4 py-3">
                    <Info className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                    <p className="text-xs text-amber-300/80 leading-relaxed">
                      ML models are loaded once at startup. Changes to model selection require a server restart. The embedding model and NLI models run on CPU - ensure sufficient RAM (≥2.5 GB).
                    </p>
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {activeSection === "retrieval" && (
            <motion.div
              key="retrieval"
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              className="glass rounded-2xl overflow-hidden"
            >
              <div className="px-6 py-4 border-b border-white/[0.06] flex items-center gap-2">
                <Database className="h-4 w-4 text-cyan-400" />
                <p className="font-semibold text-white text-sm">Retrieval Configuration</p>
              </div>
              <div className="px-6">
                <SettingRow label="BM25 Top-K" description="Number of candidates to retrieve from BM25. Must be ≥ RRF top-K. Default: 100.">
                  <NumberInput value={bm25TopK} onChange={setBm25TopK} min={10} max={500} step={10} />
                </SettingRow>
                <SettingRow label="Dense Top-K" description="Number of candidates to retrieve from Qdrant dense search. Must be ≥ RRF top-K. Default: 100.">
                  <NumberInput value={denseTopK} onChange={setDenseTopK} min={10} max={500} step={10} />
                </SettingRow>
                <SettingRow label="RRF k constant" description="Reciprocal rank fusion constant. Standard value from Cormack et al. (2009) is 60. Changing requires re-benchmarking.">
                  <NumberInput value={rrfK} onChange={setRrfK} min={1} max={200} />
                </SettingRow>
                <SettingRow label="Reranker Input Size" description="Number of candidates fed to the cross-encoder. Stored in pre_rerank_top40 - must be exactly 40 to allow Stage 3 ablation without modification.">
                  <NumberInput value={rerankerTopInput} onChange={setRerankerTopInput} min={10} max={100} step={5} />
                </SettingRow>
                <SettingRow label="Reranker Output (top-k)" description="Final number of chunks after reranking. Used as retrieval context for generation.">
                  <NumberInput value={rerankerTopOutput} onChange={setRerankerTopOutput} min={1} max={20} />
                </SettingRow>
                <SettingRow label="Query Embedding Cache" description="LRU cache for query embeddings (max 1000 entries, TTL 1 hour). Reduces latency for repeated queries.">
                  <Toggle checked={embeddingCacheEnabled} onChange={setEmbeddingCacheEnabled} />
                </SettingRow>
                <SettingRow label="Temporal Filter" description="Enforce temporal validity on retrieved chunks. Architecture Constraint #8: this cannot be disabled in production.">
                  <div className="flex items-center gap-2">
                    <Toggle checked={temporalFilterEnabled} onChange={() => {}} />
                    <Badge variant="muted">Required</Badge>
                  </div>
                </SettingRow>
              </div>
            </motion.div>
          )}

          {activeSection === "thresholds" && (
            <motion.div
              key="thresholds"
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              className="glass rounded-2xl overflow-hidden"
            >
              <div className="px-6 py-4 border-b border-white/[0.06] flex items-center gap-2">
                <Sliders className="h-4 w-4 text-emerald-400" />
                <p className="font-semibold text-white text-sm">NLI Classification Thresholds</p>
              </div>
              <div className="px-6">
                <div className="py-4 mb-2">
                  <div className="rounded-xl bg-white/[0.02] border border-white/[0.06] p-4 font-mono text-xs text-slate-400 space-y-1">
                    <p className="text-slate-500 mb-2">// 3-class heuristic (from MVP spec)</p>
                    <p><span className="text-cyan-300">supported</span>: entailment_prob <span className="text-emerald-400">&gt; {entailmentThreshold}</span></p>
                    <p><span className="text-red-300">contradicted</span>: contradiction_prob <span className="text-red-400">&gt; {contradictionThreshold}</span> AND neutral <span className="text-slate-500">&lt; 0.30</span></p>
                    <p><span className="text-amber-300">ambiguous_conditional</span>: neutral_prob <span className="text-amber-400">&gt; {neutralThreshold}</span> AND contradiction between 0.30 and 0.70</p>
                    <p><span className="text-slate-400">unresolved</span>: none of the above</p>
                  </div>
                </div>

                <SettingRow label="Entailment Threshold" description="Minimum entailment probability to classify a claim as 'supported'. Spec default: 0.65.">
                  <NumberInput value={entailmentThreshold} onChange={setEntailmentThreshold} min={0.1} max={0.99} step={0.01} />
                </SettingRow>
                <SettingRow label="Contradiction Threshold" description="Minimum contradiction probability to classify as 'contradicted' (requires neutral < 0.30). Spec default: 0.85.">
                  <NumberInput value={contradictionThreshold} onChange={setContradictionThreshold} min={0.1} max={0.99} step={0.01} />
                </SettingRow>
                <SettingRow label="Neutral Threshold (ambiguous)" description="Minimum neutral probability for 'ambiguous_conditional' classification. Spec default: 0.40.">
                  <NumberInput value={neutralThreshold} onChange={setNeutralThreshold} min={0.1} max={0.99} step={0.01} />
                </SettingRow>
              </div>
            </motion.div>
          )}

          {activeSection === "security" && (
            <motion.div
              key="security"
              initial={{ opacity: 0, x: 16 }}
              animate={{ opacity: 1, x: 0 }}
              className="glass rounded-2xl overflow-hidden"
            >
              <div className="px-6 py-4 border-b border-white/[0.06] flex items-center gap-2">
                <Shield className="h-4 w-4 text-red-400" />
                <p className="font-semibold text-white text-sm">Security Configuration</p>
              </div>
              <div className="px-6">
                <SettingRow label="CORS Allowed Origins" description='Comma-separated list of allowed origins. Use "*" for development only. In production, set to your specific frontend origin.'>
                  <input
                    className="w-48 bg-white/5 border border-white/[0.08] rounded-lg px-3 py-1.5 text-sm text-white focus:outline-none focus:border-cyan-500/40"
                    value={corsOrigins}
                    onChange={(e) => setCorsOrigins(e.target.value)}
                  />
                </SettingRow>
                <SettingRow label="Evidence Log HTTP Access" description="Expose evidence log entries over HTTP. Warning: logs contain query text. Requires access control before enabling.">
                  <div className="flex items-center gap-2">
                    <Toggle checked={evidenceLogAccess} onChange={setEvidenceLogAccess} />
                    {evidenceLogAccess && <Badge variant="danger">Warning</Badge>}
                  </div>
                </SettingRow>

                <div className="py-4">
                  <div className="space-y-2">
                    {[
                      "ANTHROPIC_API_KEY is the only secret - stored in .env, never logged",
                      "Exception handlers never expose internal tracebacks to HTTP responses",
                      "Authentication is out of scope for the MVP",
                      "Corpus documents are public-domain - no PII in corpus",
                    ].map((note) => (
                      <div key={note} className="flex items-start gap-2 text-xs text-slate-500">
                        <CheckCircle2 className="h-3.5 w-3.5 text-slate-600 shrink-0 mt-0.5" />
                        <span>{note}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </div>
      </div>

      {/* Environment info */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="glass rounded-2xl p-5"
      >
        <p className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
          <Settings className="h-4 w-4 text-slate-400" />
          Runtime Environment
        </p>
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: "Environment", value: "development" },
            { label: "Phase", value: "Phase 7 (complete)" },
            { label: "API workers", value: "1 (single-worker)" },
            { label: "OTel export", value: "disabled (dev mode)" },
          ].map(({ label, value }) => (
            <div key={label}>
              <p className="text-xs text-slate-500">{label}</p>
              <p className="text-sm text-slate-300 font-mono mt-0.5">{value}</p>
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
