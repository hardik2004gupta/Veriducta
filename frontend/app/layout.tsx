import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";
import { Toaster } from "@/components/ui/sonner";

export const metadata: Metadata = {
  title: {
    default: "Veriducta — RAG Pipeline Observability",
    template: "%s | Veriducta",
  },
  description:
    "Causal root-cause attribution for RAG answer failures. Identify which pipeline stage — chunking, retrieval, reranking, or generation — caused a degraded answer.",
  keywords: [
    "RAG",
    "LLM",
    "observability",
    "causal attribution",
    "retrieval augmented generation",
    "AI evaluation",
    "pipeline debugging",
  ],
  authors: [{ name: "Hardik Gupta" }],
  creator: "Hardik Gupta",
  openGraph: {
    type: "website",
    locale: "en_US",
    title: "Veriducta — RAG Pipeline Observability",
    description:
      "Root-cause every failed RAG answer. Causal attribution across chunking, retrieval, reranking, and generation.",
    siteName: "Veriducta",
  },
  twitter: {
    card: "summary_large_image",
    title: "Veriducta — RAG Pipeline Observability",
    description: "Root-cause every failed RAG answer with four-stage causal ablation.",
  },
  robots: {
    index: true,
    follow: true,
  },
};

export const viewport: Viewport = {
  themeColor: "#0a0f1e",
  colorScheme: "dark",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background font-sans antialiased">
        <Providers>
          {children}
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
