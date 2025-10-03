// Preview-only guard: prevent automatic /api calls from triggering console errors
// in Vite preview (no proxy). This helps keep UX health checks clean when the
// backend isn’t running. No effect in dev or production.

import { isPreview } from "@/lib/env";

declare global {
  // eslint-disable-next-line no-var
  var __previewFetchPatched: boolean | undefined;
}

try {
  if (typeof window !== "undefined" && isPreview() && !globalThis.__previewFetchPatched) {
    const origFetch = window.fetch.bind(window);
    window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
      try {
        const url = typeof input === "string" ? input : (input as Request).url;
        if (url.startsWith("/api/")) {
          // Return a no-op 204 response with a small JSON body to avoid network errors.
          const body = JSON.stringify({ ok: false, preview: true, skipped: true, url });
          return Promise.resolve(
            new Response(body, { status: 204, headers: { "Content-Type": "application/json" } })
          );
        }
      } catch {
        // fall through to origFetch on any parsing error
      }
      return origFetch(input as any, init as any);
    };
    globalThis.__previewFetchPatched = true;
  }
} catch {
  // best-effort only
}
