import type { HealthResponse, QueryRequest, QueryResponse } from "@/types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "/api/backend";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    next: { revalidate: 30 },
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${res.statusText}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${res.statusText}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => get<HealthResponse>("/health"),
  version: () => get<{ version: string; service: string; env: string }>("/version"),
  query: (req: QueryRequest) => post<QueryResponse>("/query", req),
};

export async function checkBackendHealth(): Promise<boolean> {
  try {
    const h = await api.health();
    return h.status === "ok";
  } catch {
    return false;
  }
}
