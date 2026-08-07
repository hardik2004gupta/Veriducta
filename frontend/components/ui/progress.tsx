import { cn } from "@/lib/utils";

interface ProgressProps {
  value: number;
  max?: number;
  className?: string;
  trackClassName?: string;
  color?: "cyan" | "emerald" | "violet" | "amber" | "red";
}

const colorClasses: Record<string, string> = {
  cyan: "bg-gradient-to-r from-cyan-500 to-teal-400",
  emerald: "bg-gradient-to-r from-emerald-500 to-green-400",
  violet: "bg-gradient-to-r from-violet-500 to-purple-400",
  amber: "bg-gradient-to-r from-amber-500 to-yellow-400",
  red: "bg-gradient-to-r from-red-500 to-rose-400",
};

export function Progress({
  value,
  max = 1,
  className,
  trackClassName,
  color = "cyan",
}: ProgressProps) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className={cn("h-1.5 w-full rounded-full bg-white/10", trackClassName)}>
      <div
        className={cn("h-full rounded-full transition-all duration-500", colorClasses[color], className)}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
