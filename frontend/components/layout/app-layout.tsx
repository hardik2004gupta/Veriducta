import { Sidebar } from "./sidebar";

export function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-background grid-bg">
      {/* Grid overlay */}
      <div className="pointer-events-none fixed inset-0 bg-background/60" />

      {/* Radial glow */}
      <div className="pointer-events-none fixed left-1/2 top-0 -translate-x-1/2 h-px w-3/4 bg-gradient-to-r from-transparent via-cyan-500/30 to-transparent" />
      <div className="pointer-events-none fixed -left-1/4 top-1/3 h-96 w-96 rounded-full bg-cyan-500/5 blur-3xl" />
      <div className="pointer-events-none fixed -right-1/4 bottom-1/3 h-96 w-96 rounded-full bg-violet-500/5 blur-3xl" />

      <Sidebar />

      <main className="relative flex flex-1 flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto scrollbar-thin px-8 py-8">
          {children}
        </div>
      </main>
    </div>
  );
}
