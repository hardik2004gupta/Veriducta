"use client";

import { motion } from "framer-motion";
import {
  Activity,
  Brain,
  Clock,
  DollarSign,
  GitBranch,
  Shield,
  TrendingUp,
  Zap,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardValue } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import {
  MOCK_DASHBOARD_STATS,
  MOCK_LATENCY_HISTORY,
  MOCK_COST_HISTORY,
  MOCK_FAITHFULNESS_HISTORY,
  MOCK_ROOT_CAUSE_DISTRIBUTION,
  MOCK_RECENT_QUERIES,
} from "@/lib/mock-data";

// ── Animation ─────────────────────────────────────────────────────────────────

const stagger = {
  visible: { transition: { staggerChildren: 0.07 } },
};
const item = {
  hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4 } },
};

// ── Stat card ─────────────────────────────────────────────────────────────────

interface StatCardProps {
  icon: React.ElementType;
  title: string;
  value: string;
  sub?: string;
  trend?: { value: string; positive: boolean };
  color: "cyan" | "emerald" | "violet" | "amber";
}

const colorStyles: Record<string, { icon: string; glow: string }> = {
  cyan: { icon: "text-cyan-400 bg-cyan-500/10", glow: "shadow-cyan-500/10" },
  emerald: { icon: "text-emerald-400 bg-emerald-500/10", glow: "shadow-emerald-500/10" },
  violet: { icon: "text-violet-400 bg-violet-500/10", glow: "shadow-violet-500/10" },
  amber: { icon: "text-amber-400 bg-amber-500/10", glow: "shadow-amber-500/10" },
};

function StatCard({ icon: Icon, title, value, sub, trend, color }: StatCardProps) {
  const styles = colorStyles[color];
  return (
    <Card className={`hover:shadow-lg ${styles.glow} transition-shadow duration-300`}>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${styles.icon}`}>
          <Icon className="h-4.5 w-4.5" />
        </div>
      </CardHeader>
      <CardValue>{value}</CardValue>
      {sub && <p className="mt-1 text-xs text-slate-500">{sub}</p>}
      {trend && (
        <div className={`mt-2 flex items-center gap-1 text-xs font-medium ${trend.positive ? "text-emerald-400" : "text-red-400"}`}>
          <TrendingUp className={`h-3.5 w-3.5 ${!trend.positive ? "rotate-180" : ""}`} />
          {trend.value}
        </div>
      )}
    </Card>
  );
}

// ── Chart tooltip ─────────────────────────────────────────────────────────────

function ChartTooltip({ active, payload, label, unit = "" }: {
  active?: boolean;
  payload?: Array<{ value: number; color: string; name: string }>;
  label?: string;
  unit?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="glass rounded-xl px-3 py-2 text-xs">
      <p className="text-slate-400 mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }} className="font-semibold">
          {p.name}: {p.value}{unit}
        </p>
      ))}
    </div>
  );
}

// ── Root cause pie colours ────────────────────────────────────────────────────

const PIE_COLORS = ["#06b6d4", "#8b5cf6", "#f59e0b", "#10b981"];

// ── Page ──────────────────────────────────────────────────────────────────────

export default function DashboardPage() {
  const stats = MOCK_DASHBOARD_STATS;

  return (
    <div className="space-y-8">
      {/* Header */}
      <motion.div initial="hidden" animate="visible" variants={stagger}>
        <motion.div variants={item} className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black text-white">Pipeline Dashboard</h1>
            <p className="text-sm text-slate-500 mt-0.5">Real-time RAG pipeline observability · last updated just now</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 glass rounded-xl px-3 py-2">
              <Activity className="h-4 w-4 text-emerald-400 animate-pulse" />
              <span className="text-sm text-emerald-400 font-medium">All systems operational</span>
            </div>
            <Badge variant="muted">v1.0.0</Badge>
          </div>
        </motion.div>
      </motion.div>

      {/* Stat cards */}
      <motion.div
        initial="hidden"
        animate="visible"
        variants={stagger}
        className="grid grid-cols-2 gap-4 xl:grid-cols-4"
      >
        <motion.div variants={item}>
          <StatCard
            icon={Activity}
            title="Total Queries"
            value={stats.total_queries.toLocaleString()}
            sub="all time"
            trend={{ value: "+12.3% this week", positive: true }}
            color="cyan"
          />
        </motion.div>
        <motion.div variants={item}>
          <StatCard
            icon={Shield}
            title="Faithfulness"
            value={`${(stats.faithfulness * 100).toFixed(1)}%`}
            sub="citation entailment rate"
            trend={{ value: "+0.8% vs baseline", positive: true }}
            color="emerald"
          />
        </motion.div>
        <motion.div variants={item}>
          <StatCard
            icon={Brain}
            title="Root-Cause Accuracy"
            value={`${(stats.root_cause_accuracy * 100).toFixed(1)}%`}
            sub="60-case benchmark"
            trend={{ value: "+3.1% vs RAGAS", positive: true }}
            color="violet"
          />
        </motion.div>
        <motion.div variants={item}>
          <StatCard
            icon={DollarSign}
            title="Total Cost"
            value={`$${stats.total_cost_usd.toFixed(2)}`}
            sub="Claude Sonnet 4.6 · all time"
            trend={{ value: "−8% per query vs last week", positive: true }}
            color="amber"
          />
        </motion.div>
      </motion.div>

      {/* Secondary stats */}
      <motion.div
        initial="hidden"
        animate="visible"
        variants={stagger}
        className="grid grid-cols-4 gap-4"
      >
        {[
          { label: "Recall@5", value: stats.recall_at_5, color: "cyan" as const },
          { label: "Omission Rate", value: stats.omission_rate, inverse: true, color: "emerald" as const },
          { label: "Temporal Precision", value: stats.temporal_precision, color: "violet" as const },
          { label: "Contradiction Ack Rate", value: stats.contradiction_ack_rate, color: "amber" as const },
        ].map(({ label, value, inverse, color }) => (
          <motion.div key={label} variants={item} className="glass rounded-2xl p-4">
            <p className="text-xs text-slate-500 mb-3">{label}</p>
            <p className="text-2xl font-black text-white mb-2">
              {`${(value * 100).toFixed(1)}%`}
            </p>
            <Progress value={inverse ? 1 - value : value} color={color} />
          </motion.div>
        ))}
      </motion.div>

      {/* Charts row */}
      <motion.div
        initial="hidden"
        animate="visible"
        variants={stagger}
        className="grid grid-cols-12 gap-4"
      >
        {/* Latency chart */}
        <motion.div variants={item} className="col-span-5 glass rounded-2xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="font-semibold text-white text-sm">Query Latency</p>
              <p className="text-xs text-slate-500">p50 / p95 · last 24h</p>
            </div>
            <div className="flex items-center gap-1 glass rounded-lg px-2 py-1">
              <Clock className="h-3.5 w-3.5 text-slate-400" />
              <span className="text-xs text-slate-400">3.4s p50</span>
            </div>
          </div>
          <ResponsiveContainer width="100%" height={160}>
            <AreaChart data={MOCK_LATENCY_HISTORY} margin={{ top: 5, right: 0, left: -30, bottom: 0 }}>
              <defs>
                <linearGradient id="p50grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.3} />
                  <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="p95grad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.2} />
                  <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
              <XAxis dataKey="time" tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltip unit="s" />} />
              <Area type="monotone" dataKey="p50" name="p50" stroke="#06b6d4" strokeWidth={2} fill="url(#p50grad)" />
              <Area type="monotone" dataKey="p95" name="p95" stroke="#8b5cf6" strokeWidth={2} fill="url(#p95grad)" />
            </AreaChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Cost chart */}
        <motion.div variants={item} className="col-span-4 glass rounded-2xl p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <p className="font-semibold text-white text-sm">Daily Cost</p>
              <p className="text-xs text-slate-500">USD · Claude Sonnet 4.6</p>
            </div>
            <Zap className="h-4 w-4 text-amber-400" />
          </div>
          <ResponsiveContainer width="100%" height={160}>
            <BarChart data={MOCK_COST_HISTORY} margin={{ top: 5, right: 0, left: -30, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip content={<ChartTooltip unit="$" />} />
              <Bar dataKey="cost" name="cost" fill="#f59e0b" radius={[4, 4, 0, 0]} opacity={0.85} />
            </BarChart>
          </ResponsiveContainer>
        </motion.div>

        {/* Root cause pie */}
        <motion.div variants={item} className="col-span-3 glass rounded-2xl p-5">
          <div className="mb-4">
            <p className="font-semibold text-white text-sm">Root Causes</p>
            <p className="text-xs text-slate-500">all attributed failures</p>
          </div>
          <ResponsiveContainer width="100%" height={120}>
            <PieChart>
              <Pie
                data={MOCK_ROOT_CAUSE_DISTRIBUTION}
                cx="50%"
                cy="50%"
                innerRadius={36}
                outerRadius={54}
                paddingAngle={3}
                dataKey="value"
              >
                {MOCK_ROOT_CAUSE_DISTRIBUTION.map((_entry, index) => (
                  <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value: number) => [`${value}%`, ""]} />
            </PieChart>
          </ResponsiveContainer>
          <div className="space-y-1.5 mt-2">
            {MOCK_ROOT_CAUSE_DISTRIBUTION.map((d, i) => (
              <div key={d.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-1.5">
                  <div className="h-2 w-2 rounded-full" style={{ backgroundColor: PIE_COLORS[i] }} />
                  <span className="text-slate-400">{d.name}</span>
                </div>
                <span className="text-slate-300 font-medium">{d.value}%</span>
              </div>
            ))}
          </div>
        </motion.div>
      </motion.div>

      {/* Faithfulness history */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.35 }}
        className="glass rounded-2xl p-5"
      >
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="font-semibold text-white text-sm">Faithfulness & Recall@5</p>
            <p className="text-xs text-slate-500">30-day trend · citation entailment + retrieval recall</p>
          </div>
          <div className="flex items-center gap-4 text-xs">
            <div className="flex items-center gap-1.5">
              <div className="h-2 w-2 rounded-full bg-emerald-400" />
              <span className="text-slate-400">Faithfulness</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-2 w-2 rounded-full bg-cyan-400" />
              <span className="text-slate-400">Recall@5</span>
            </div>
          </div>
        </div>
        <ResponsiveContainer width="100%" height={140}>
          <AreaChart data={MOCK_FAITHFULNESS_HISTORY} margin={{ top: 5, right: 0, left: -30, bottom: 0 }}>
            <defs>
              <linearGradient id="faithgrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#10b981" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
              </linearGradient>
              <linearGradient id="recallgrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#06b6d4" stopOpacity={0.2} />
                <stop offset="95%" stopColor="#06b6d4" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
            <XAxis dataKey="date" tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
            <YAxis domain={[0.6, 1.0]} tick={{ fill: "#475569", fontSize: 10 }} axisLine={false} tickLine={false} />
            <Tooltip content={<ChartTooltip />} />
            <Area type="monotone" dataKey="faithfulness" name="Faithfulness" stroke="#10b981" strokeWidth={2} fill="url(#faithgrad)" />
            <Area type="monotone" dataKey="recall" name="Recall@5" stroke="#06b6d4" strokeWidth={2} fill="url(#recallgrad)" />
          </AreaChart>
        </ResponsiveContainer>
      </motion.div>

      {/* Recent queries */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.42 }}
        className="glass rounded-2xl overflow-hidden"
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/[0.06]">
          <p className="font-semibold text-white text-sm">Recent Queries</p>
          <a href="/evidence" className="flex items-center gap-1 text-xs text-slate-400 hover:text-cyan-400 transition-colors">
            View all <ChevronRight className="h-3.5 w-3.5" />
          </a>
        </div>
        <div className="divide-y divide-white/[0.04]">
          {MOCK_RECENT_QUERIES.map((q) => (
            <div key={q.id} className="flex items-center gap-4 px-5 py-3.5 hover:bg-white/[0.02] transition-colors cursor-pointer group">
              <div className="flex-1 min-w-0">
                <p className="text-sm text-slate-200 truncate group-hover:text-white transition-colors">{q.query}</p>
                <p className="text-xs text-slate-600 mt-0.5">{q.timestamp}</p>
              </div>
              <div className="flex items-center gap-3 shrink-0">
                <span className="text-xs text-slate-500">{q.latency_ms}ms</span>
                <span className="text-xs text-slate-500">${q.cost_usd.toFixed(4)}</span>
                {q.flagged ? (
                  <div className="flex items-center gap-1 rounded-full bg-red-500/10 border border-red-500/20 px-2 py-0.5">
                    <AlertTriangle className="h-3 w-3 text-red-400" />
                    <span className="text-xs text-red-400">Review</span>
                  </div>
                ) : (
                  <div className="flex items-center gap-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5">
                    <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                    <span className="text-xs text-emerald-400">Verified</span>
                  </div>
                )}
              </div>
              <ChevronRight className="h-4 w-4 text-slate-700 group-hover:text-slate-400 transition-colors" />
            </div>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
