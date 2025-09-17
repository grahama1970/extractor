import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import React, { useEffect, useState } from "react";
import Index from "./pages/Index";
import ClassicLayout from "./pages/ClassicLayout";
import TabbedLayout from "./pages/TabbedLayout";
import DashboardLayout from "./pages/DashboardLayout";
import NotFound from "./pages/NotFound";
import ExtractPage from "./pages/ExtractPage";
import AskPage from "./pages/AskPage";

const queryClient = new QueryClient();

function BuildChip() {
  const [data, setData] = useState<any>(null);
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch('/build.json', { cache: 'no-store' });
        const j = await r.json();
        setData(j);
      } catch { /* no-op */ }
    })();
  }, []);
  if (!data) return null;
  const ts = (() => { try { return new Date(data.built_at).toLocaleTimeString(); } catch { return data.built_at; } })();
  return (
    <div aria-label="build-info" className="fixed bottom-2 left-2 z-50 pointer-events-none text-[10px] text-muted-foreground bg-card/90 border rounded px-2 py-0.5">
      {(data.git || 'dev') + ' · ' + ts}
    </div>
  );
}

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <Toaster />
      <Sonner />
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Index />} />
          <Route path="/classic" element={<ClassicLayout />} />
          <Route path="/main" element={<ClassicLayout />} />
          <Route path="/tabbed" element={<TabbedLayout />} />
          <Route path="/dashboard" element={<DashboardLayout />} />
          <Route path="/extract" element={<ExtractPage />} />
          <Route path="/ask" element={<AskPage />} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<NotFound />} />
        </Routes>
      </BrowserRouter>
      <BuildChip />
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
