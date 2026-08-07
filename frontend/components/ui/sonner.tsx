"use client";

import { Toaster as SonnerToaster } from "sonner";

export function Toaster() {
  return (
    <SonnerToaster
      position="bottom-right"
      theme="dark"
      toastOptions={{
        style: {
          background: "hsl(222 47% 10%)",
          border: "1px solid hsl(217 33% 16%)",
          color: "hsl(210 40% 98%)",
        },
      }}
    />
  );
}
