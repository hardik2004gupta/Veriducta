"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  MessageSquare,
  Search,
  GitBranch,
  BarChart3,
  FileText,
  Settings,
  Activity,
  Zap,
  ChevronRight,
} from "lucide-react";

const NAV = [
  { href: "/dashboard", icon: LayoutDashboard, label: "Dashboard" },
  { href: "/ask", icon: MessageSquare, label: "Ask Veriducta" },
  { href: "/retrieval", icon: Search, label: "Retrieval Inspector" },
  { href: "/replay", icon: GitBranch, label: "Replay Viewer" },
  { href: "/evaluation", icon: BarChart3, label: "Evaluation" },
  { href: "/evidence", icon: FileText, label: "Evidence Log" },
  { href: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-64 flex-col border-r border-white/[0.06] bg-background/80 backdrop-blur-xl">
      {/* Logo */}
      <div className="flex items-center gap-3 px-5 py-6 border-b border-white/[0.06]">
        <div className="relative">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500 to-teal-600 shadow-lg shadow-cyan-500/30">
            <Zap className="h-5 w-5 text-white" />
          </div>
          <span className="absolute -right-1 -top-1 flex h-3 w-3">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-3 w-3 rounded-full bg-emerald-500" />
          </span>
        </div>
        <div>
          <p className="font-bold text-white tracking-tight">Veriducta</p>
          <p className="text-[10px] text-slate-500 uppercase tracking-widest">RAG Observability</p>
        </div>
      </div>

      {/* Status pill */}
      <div className="mx-4 mt-4">
        <div className="flex items-center gap-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 px-3 py-2">
          <Activity className="h-3.5 w-3.5 text-emerald-400" />
          <span className="text-xs text-emerald-400 font-medium">Pipeline Healthy</span>
        </div>
      </div>

      {/* Nav */}
      <nav className="mt-4 flex-1 space-y-1 px-3 pb-4">
        {NAV.map(({ href, icon: Icon, label }) => {
          const active = pathname === href || pathname.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={cn(
                "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200",
                active
                  ? "bg-gradient-to-r from-cyan-500/20 to-teal-500/10 text-cyan-300 border border-cyan-500/20"
                  : "text-slate-400 hover:bg-white/5 hover:text-slate-200",
              )}
            >
              <Icon
                className={cn(
                  "h-4 w-4 transition-colors",
                  active ? "text-cyan-400" : "text-slate-500 group-hover:text-slate-300",
                )}
              />
              <span className="flex-1">{label}</span>
              {active && <ChevronRight className="h-3 w-3 text-cyan-400/60" />}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="border-t border-white/[0.06] px-5 py-4">
        <p className="text-[10px] text-slate-600 uppercase tracking-widest">v0.1.0 · Phase 7</p>
      </div>
    </aside>
  );
}
