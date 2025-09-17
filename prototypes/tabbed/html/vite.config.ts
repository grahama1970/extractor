import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

// https://vitejs.dev/config/
async function detectProxyTarget(): Promise<string> {
  if (process.env.VITE_API_PROXY) return process.env.VITE_API_PROXY;
  const candidates = [
    'http://127.0.0.1:8000',
    'http://localhost:8000',
    'http://127.0.0.1:8001',
    'http://localhost:8001',
  ];
  for (const base of candidates) {
    try {
      const r = await fetch(base + '/api/build', { method: 'GET', signal: AbortSignal.timeout(300) });
      if (r.ok) return base;
    } catch {}
  }
  return 'http://localhost:8000';
}

export default defineConfig(async ({ mode }) => ({
  server: {
    host: "0.0.0.0",
    port: 8080,
    strictPort: true,
    headers: mode === "development" ? {
      "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
      "Pragma": "no-cache",
      "Expires": "0",
      "Surrogate-Control": "no-store",
    } : undefined,
    proxy: {
      // Proxy API calls during dev to FastAPI backend (uvicorn on :8000)
      "/api": {
        target: await detectProxyTarget(),
        changeOrigin: true,
        // Keep the /api prefix so backend endpoints like /api/health resolve correctly
      },
      "/ws": {
        target: await detectProxyTarget(),
        changeOrigin: true,
        ws: true,
      },
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 8080,
    strictPort: true,
    headers: {
      "Cache-Control": "no-store, no-cache, must-revalidate, proxy-revalidate",
      "Pragma": "no-cache",
      "Expires": "0",
      "Surrogate-Control": "no-store",
    },
  },
  plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
