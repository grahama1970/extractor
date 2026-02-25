import React, { createContext, useContext, useCallback, useEffect, useMemo, useState } from "react";
import { PERSONAS, type PersonaId, type PersonaConfig } from "@/lib/persona-config";
import { useViewDistance, type ViewDistance } from "@/hooks/useViewDistance";

const STORAGE_KEY = "embry-persona";
const DEFAULT_PERSONA: PersonaId = "embry";

type PersonaContextValue = {
  persona: PersonaId;
  setPersona: (id: PersonaId) => void;
  config: PersonaConfig;
  distance: ViewDistance;
};

const Ctx = createContext<PersonaContextValue | null>(null);

function readStored(): PersonaId {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    if (v && v in PERSONAS) return v as PersonaId;
  } catch { /* SSR / privacy mode */ }
  return DEFAULT_PERSONA;
}

export function PersonaProvider({
  children,
  detectedPersona,
}: {
  children: React.ReactNode;
  /** Override from webcam/voice detection — when set, takes precedence over localStorage. */
  detectedPersona?: PersonaId | null;
}) {
  const [persona, setPersonaRaw] = useState<PersonaId>(readStored);
  const distance = useViewDistance();

  // External detection overrides manual selection
  useEffect(() => {
    if (detectedPersona && detectedPersona in PERSONAS) {
      setPersonaRaw(detectedPersona);
    }
  }, [detectedPersona]);

  const setPersona = useCallback((id: PersonaId) => {
    setPersonaRaw(id);
    try { localStorage.setItem(STORAGE_KEY, id); } catch { /* noop */ }
  }, []);

  // Inject CSS custom property for accent color
  useEffect(() => {
    const cfg = PERSONAS[persona];
    document.documentElement.style.setProperty("--persona-accent", cfg.accent);
  }, [persona]);

  const value = useMemo<PersonaContextValue>(() => ({
    persona,
    setPersona,
    config: PERSONAS[persona],
    distance,
  }), [persona, setPersona, distance]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function usePersona(): PersonaContextValue {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("usePersona must be used within <PersonaProvider>");
  return ctx;
}
