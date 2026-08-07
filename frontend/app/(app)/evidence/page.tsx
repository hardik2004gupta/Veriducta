"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { Search, Filter, FileText, ChevronRight, CheckCircle2, AlertTriangle, Clock, Database } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { MOCK_RECENT_QUERIES } from "@/lib/mock-data";

// ── Mock evidence entries ─────────────────────────────────────────────────────

const EVIDENCE_ENTRIES = [
  {
    trace_id: "3f9a2c1e-4b7d-4a8e-9c1f-2d3e4f5a6b7c",
    query: "What are the OSHA permissible exposure limits for respirable crystalline silica?",
    timestamp: "2026-08-07T10:23:14Z",
    quality_score: 0.74,
    flagged: false,
    latency_ms: 3240,
    cost_usd: 0.0042,
    claims: 3,
    verified: 3,
    log_file: "2026-08-07.jsonl",
    byte_offset: 108432,
  },
  {
    trace_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    query: "How does NIST define measurement uncertainty for indirect measurements?",
    timestamp: "2026-08-07T09:47:33Z",
    quality_score: 0.61,
    flagged: true,
    latency_ms: 4810,
    cost_usd: 0.0065,
    claims: 4,
    verified: 3,
    log_file: "2026-08-07.jsonl",
    byte_offset: 82019,
  },
  {
    trace_id: "b2c3d4e5-f6a7-8901-bcde-f23456789012",
    query: "What geotechnical criteria apply to seismic site classification for Site Class D?",
    timestamp: "2026-08-07T09:12:55Z",
    quality_score: 0.88,
    flagged: false,
    latency_ms: 2980,
    cost_usd: 0.0038,
    claims: 5,
    verified: 5,
    log_file: "2026-08-07.jsonl",
    byte_offset: 54127,
  },
  ...MOCK_RECENT_QUERIES.slice(0, 3).map((q, i) => ({
    trace_id: crypto.randomUUID(),
    query: q.query,
    timestamp: q.timestamp,
    quality_score: 0.7 + Math.random() * 0.2,
    flagged: q.flagged,
    latency_ms: q.latency_ms,
    cost_usd: q.cost_usd,
    claims: Math.floor(Math.random() * 4) + 2,
    verified: Math.floor(Math.random() * 4) + 1,
    log_file: "2026-08-07.jsonl",
    byte_offset: 10000 + i * 15000,
  })),
];

// ── Log entry expanded ────────────────────────────────────────────────────────

interface EntryProps {
  entry: typeof EVIDENCE_ENTRIES[number];
}

function EntryRow({ entry }: EntryProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className={cn("border-b border-white/[0.04] last:border-0 transition-colors", entry.flagged ? "bg-red-500/[0.02]" : "hover:bg-white/[0.02]")}>
      <button onClick={() => setOpen(!open)} className="w-full flex items-center gap-4 px-5 py-4 text-left">
        {/* Status indicator */}
        <div className="shrink-0">
          {entry.flagged ? (
            <AlertTriangle className="h-4 w-4 text-amber-400" />
          ) : (
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          )}
        </div>

        {/* Query */}
        <div className="flex-1 min-w-0">
          <p className="text-sm text-slate-200 truncate">{entry.query}</p>
          <div className="flex items-center gap-3 mt-1 text-xs text-slate-600">
            <code className="text-cyan-500">{entry.trace_id.slice(0, 12)}…</code>
            <span>{new Date(entry.timestamp).toLocaleString()}</span>
          </div>
        </div>

        {/* Stats */}
        <div className="flex items-center gap-4 shrink-0">
          <div className="text-center">
            <p className={cn("text-sm font-bold tabular-nums", entry.quality_score >= 0.75 ? "text-emerald-400" : entry.quality_score >= 0.6 ? "text-amber-400" : "text-red-400")}>
              {entry.quality_score.toFixed(2)}
            </p>
            <p className="text-[10px] text-slate-600">quality</p>
          </div>
          <div className="text-center">
            <p className="text-sm font-bold text-slate-300 tabular-nums">{entry.latency_ms}ms</p>
            <p className="text-[10px] text-slate-600">latency</p>
          </div>
          <div className="text-center">
            <p className="text-sm font-bold text-slate-300">{entry.verified}/{entry.claims}</p>
            <p className="text-[10px] text-slate-600">claims</p>
          </div>
          {entry.flagged && <Badge variant="warning">Review</Badge>}
        </div>

        <ChevronRight className={cn("h-4 w-4 text-slate-600 transition-transform", open ? "rotate-90" : "")} />
      </button>

      {open && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: "auto", opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          className="border-t border-white/[0.04] px-5 py-5 bg-white/[0.01]"
        >
          <div className="grid grid-cols-3 gap-6">
            {/* Trace info */}
            <div className="space-y-3">
              <p className="text-xs text-slate-500 uppercase tracking-wider">Trace Details</p>
              {[
                { label: "Trace ID", value: entry.trace_id },
                { label: "Log file", value: entry.log_file },
                { label: "Byte offset", value: entry.byte_offset.toLocaleString() },
                { label: "Estimated cost", value: `$${entry.cost_usd.toFixed(5)}` },
              ].map(({ label, value }) => (
                <div key={label}>
                  <p className="text-xs text-slate-600">{label}</p>
                  <code className="text-xs text-slate-300">{value}</code>
                </div>
              ))}
            </div>

            {/* Claims */}
            <div className="space-y-3">
              <p className="text-xs text-slate-500 uppercase tracking-wider">Claim Verification</p>
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-400">Supported</span>
                  <span className="text-emerald-400 font-medium">{entry.verified}</span>
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-400">Unverified</span>
                  <span className="text-amber-400 font-medium">{entry.claims - entry.verified}</span>
                </div>
                <div className="flex items-center justify-between text-sm border-t border-white/[0.06] pt-2">
                  <span className="text-slate-400">Total claims</span>
                  <span className="text-white font-medium">{entry.claims}</span>
                </div>
              </div>
            </div>

            {/* Actions */}
            <div className="space-y-3">
              <p className="text-xs text-slate-500 uppercase tracking-wider">Actions</p>
              <div className="space-y-2">
                <Button variant="outline" size="sm" className="w-full justify-start">
                  <FileText className="h-4 w-4" /> View full trace JSON
                </Button>
                <Button variant="outline" size="sm" className="w-full justify-start">
                  <ChevronRight className="h-4 w-4" /> Open in Replay Viewer
                </Button>
                {entry.flagged && (
                  <Button variant="ghost" size="sm" className="w-full justify-start text-amber-400 hover:text-amber-300">
                    <AlertTriangle className="h-4 w-4" /> Mark as reviewed
                  </Button>
                )}
              </div>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function EvidenceLogPage() {
  const [search, setSearch] = useState("");
  const [filter, setFilter] = useState<"all" | "flagged" | "verified">("all");

  const filtered = EVIDENCE_ENTRIES.filter((e) => {
    const matchesSearch = e.query.toLowerCase().includes(search.toLowerCase()) ||
      e.trace_id.startsWith(search);
    const matchesFilter = filter === "all" ||
      (filter === "flagged" && e.flagged) ||
      (filter === "verified" && !e.flagged);
    return matchesSearch && matchesFilter;
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black text-white">Evidence Log Explorer</h1>
            <p className="text-sm text-slate-500 mt-1">SQLite-indexed JSONL evidence log · O(1) trace lookup by byte offset</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 glass rounded-xl px-3 py-2">
              <Database className="h-4 w-4 text-slate-400" />
              <span className="text-xs text-slate-400">evidence_logs/2026-08-07.jsonl</span>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Stats */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.07 }}
        className="grid grid-cols-4 gap-4"
      >
        {[
          { label: "Total entries", value: "4,832", icon: FileText, color: "text-cyan-400 bg-cyan-500/10" },
          { label: "Flagged for review", value: "89", icon: AlertTriangle, color: "text-amber-400 bg-amber-500/10" },
          { label: "Verified clean", value: "4,743", icon: CheckCircle2, color: "text-emerald-400 bg-emerald-500/10" },
          { label: "Log files (gzipped)", value: "12", icon: Database, color: "text-violet-400 bg-violet-500/10" },
        ].map(({ label, value, icon: Icon, color }) => (
          <div key={label} className="glass rounded-2xl p-4 flex items-center gap-4">
            <div className={cn("flex h-10 w-10 items-center justify-center rounded-xl shrink-0", color)}>
              <Icon className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xl font-black text-white">{value}</p>
              <p className="text-xs text-slate-500">{label}</p>
            </div>
          </div>
        ))}
      </motion.div>

      {/* Search and filters */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.12 }}
        className="flex items-center gap-3"
      >
        <div className="flex-1 glass rounded-xl flex items-center gap-3 px-4 py-2.5">
          <Search className="h-4 w-4 text-slate-400 shrink-0" />
          <input
            className="flex-1 bg-transparent text-sm text-white placeholder-slate-600 focus:outline-none"
            placeholder="Search by query text or trace ID…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="flex items-center gap-1 glass rounded-xl p-1">
          {(["all", "flagged", "verified"] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "px-3 py-1.5 rounded-lg text-xs font-medium capitalize transition-all",
                filter === f ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/20" : "text-slate-500 hover:text-slate-300",
              )}
            >
              {f}
            </button>
          ))}
        </div>
        <Button variant="outline" size="sm">
          <Filter className="h-4 w-4" /> Date range
        </Button>
      </motion.div>

      {/* SQLite index info */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="glass rounded-2xl px-5 py-3 flex items-center gap-4"
      >
        <Database className="h-4 w-4 text-slate-500 shrink-0" />
        <div className="flex items-center gap-6 text-xs text-slate-500">
          <span>SQLite index: <code className="text-slate-400">evidence_logs/index.db</code></span>
          <span>Schema: <code className="text-slate-400">(trace_id, log_file, byte_offset, query_hash, created_at, quality_score, flagged_as_failure)</code></span>
          <span className="text-emerald-400">O(1) lookup via byte_offset seek</span>
        </div>
      </motion.div>

      {/* Entry table */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.18 }}
        className="glass rounded-2xl overflow-hidden"
      >
        {/* Header */}
        <div className="flex items-center gap-4 px-5 py-3 border-b border-white/[0.06] bg-white/[0.01]">
          <div className="w-4" />
          <span className="flex-1 text-xs text-slate-600">Query · Trace ID · Timestamp</span>
          <div className="flex items-center gap-4 shrink-0">
            <span className="text-xs text-slate-600 w-16 text-center">Quality</span>
            <span className="text-xs text-slate-600 w-16 text-center">Latency</span>
            <span className="text-xs text-slate-600 w-16 text-center">Claims</span>
            <div className="w-20" />
          </div>
          <div className="w-4" />
        </div>

        {filtered.length === 0 ? (
          <div className="text-center py-16">
            <Clock className="h-8 w-8 text-slate-700 mx-auto mb-3" />
            <p className="text-slate-500 text-sm">No entries match your search.</p>
          </div>
        ) : (
          filtered.map((entry) => <EntryRow key={entry.trace_id} entry={entry} />)
        )}

        {/* Footer */}
        <div className="px-5 py-3 border-t border-white/[0.06] bg-white/[0.01] flex items-center justify-between">
          <span className="text-xs text-slate-600">Showing {filtered.length} of {EVIDENCE_ENTRIES.length} entries</span>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm">Previous</Button>
            <Badge variant="muted">Page 1</Badge>
            <Button variant="ghost" size="sm">Next</Button>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
