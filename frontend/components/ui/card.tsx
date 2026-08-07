import { cn } from "@/lib/utils";

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  glow?: "cyan" | "emerald" | "violet" | "amber" | "none";
}

const glowClasses: Record<string, string> = {
  cyan: "hover:glow-cyan",
  emerald: "hover:glow-emerald",
  violet: "hover:glow-violet",
  amber: "hover:shadow-amber-500/20",
  none: "",
};

export function Card({ className, glow = "none", children, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "glass rounded-2xl p-6 transition-all duration-300",
        glow !== "none" && glowClasses[glow],
        className,
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("mb-4 flex items-center justify-between", className)} {...props}>
      {children}
    </div>
  );
}

export function CardTitle({ className, children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3 className={cn("text-sm font-medium text-slate-400 uppercase tracking-wider", className)} {...props}>
      {children}
    </h3>
  );
}

export function CardValue({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("text-3xl font-bold text-white tabular-nums", className)} {...props}>
      {children}
    </div>
  );
}
