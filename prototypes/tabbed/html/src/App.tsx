import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import React, { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { isDev } from "@/lib/env";
import { PersonaProvider } from "@/contexts/PersonaContext";
import PersonaShell from "@/components/PersonaShell";
import Index from "./pages/Index";
import ClassicLayout from "./pages/ClassicLayout";
import TabbedLayout from "./pages/TabbedLayout";
import DashboardLayout from "./pages/DashboardLayout";
import NotFound from "./pages/NotFound";
import ExtractPage from "./pages/ExtractPage";
import AskPage from "./pages/AskPage";
const ReviewLayout = React.lazy(() => import("./pages/ReviewLayout"));
const QuarantineView = React.lazy(() => import("./pages/QuarantineView"));
const DatalakeDashboard = React.lazy(() => import("./pages/DatalakeDashboard"));
const CrossDocSearch = React.lazy(() => import("./pages/CrossDocSearch"));

const queryClient = new QueryClient();

const LazyFallback = (
  <div className="flex items-center justify-center h-full min-h-[200px]">
    <Loader2 className="h-8 w-8 animate-spin" />
  </div>
);

function BuildChip() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    // Only fetch build info in dev; in preview there is no proxy for /api
    if (!isDev()) return;
    (async () => {
      try {
        const r = await fetch('/api/build', { cache: 'no-store' });
        const j = await r.json();
        setData(j);
      } catch { /* no-op */ }
    })();
  }, []);
  if (!isDev() || !data) return null;
  const ts = (() => { try { return new Date((data.started_at || data.built_at)).toLocaleTimeString(); } catch { return (data.started_at || data.built_at); } })();
  return (
    <div aria-label="build-info" className="fixed bottom-2 left-2 z-50 pointer-events-none text-[10px] text-muted-foreground bg-card/90 border rounded px-2 py-0.5">
      {(data.git || 'dev') + ' · ' + ts}
    </div>
  );
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <div data-testid="app-ready" style={{ display: 'none' }} />
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <PersonaProvider>
          <Routes>
            {/* Standalone routes (no persona shell) */}
            <Route path="/" element={<Index />} />
            <Route path="/classic" element={<ClassicLayout />} />
            <Route path="/main" element={<ClassicLayout />} />
            <Route path="/tabbed" element={<TabbedLayout />} />
            <Route path="/dashboard" element={<DashboardLayout />} />
            <Route path="/extract" element={<ExtractPage />} />

            {/* Persona-aware routes wrapped in PersonaShell */}
            <Route element={<PersonaShell />}>
              <Route path="/ask" element={<AskPage />} />
              <Route path="/review" element={
                <React.Suspense fallback={LazyFallback}>
                  <ReviewLayout />
                </React.Suspense>
              } />
              <Route path="/quarantine" element={
                <React.Suspense fallback={LazyFallback}>
                  <QuarantineView />
                </React.Suspense>
              } />
              <Route path="/datalake" element={
                <React.Suspense fallback={LazyFallback}>
                  <DatalakeDashboard />
                </React.Suspense>
              } />
              <Route path="/search" element={
                <React.Suspense fallback={LazyFallback}>
                  <CrossDocSearch />
                </React.Suspense>
              } />
            </Route>

            {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </PersonaProvider>
      </BrowserRouter>
      <BuildChip />
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
