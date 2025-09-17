import * as React from "react";
import { cn } from "@/lib/utils";

// Minimal ShadCN-style spinner (accessible)
export function Loader({ className, size = 16, label }: { className?: string; size?: number; label?: string }) {
  const s = `${size}px`;
  return (
    <div className={cn("inline-flex items-center gap-2", className)} role="status" aria-live="polite" aria-busy="true">
      <span
        className="inline-block rounded-full border-2 border-muted-foreground/30 border-t-primary animate-spin"
        style={{ width: s, height: s }}
      />
      {label ? <span className="sr-only">{label}</span> : null}
    </div>
  );
}

// Three-dot pulse loader
export function LoaderDots({ className, label }: { className?: string; label?: string }) {
  return (
    <div className={cn("inline-flex items-center gap-1", className)} role="status" aria-live="polite" aria-busy="true">
      <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-pulse [animation-delay:0ms]" />
      <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-pulse [animation-delay:120ms]" />
      <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground animate-pulse [animation-delay:240ms]" />
      {label ? <span className="sr-only">{label}</span> : null}
    </div>
  );
}

