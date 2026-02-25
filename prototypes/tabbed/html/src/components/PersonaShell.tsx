/**
 * PersonaShell — responsive layout wrapper with distance-specific chrome.
 *
 * 10ft (TV):   minimal top bar, large nav targets, auto-switch dashboard/review
 * 5ft (Desk):  horizontal nav bar with persona dropdown
 * Phone:       compact top bar + bottom tab nav
 */
import React from "react";
import { Outlet, NavLink, useLocation, useSearchParams } from "react-router-dom";
import {
  AlertTriangle, Database, MessageSquare, Search, FileText,
  ChevronDown, Clock,
} from "lucide-react";
import { usePersona } from "@/contexts/PersonaContext";
import { PERSONAS, PERSONA_IDS, topDimensions, type PersonaId } from "@/lib/persona-config";
import { Badge } from "@/components/ui/badge";

// --- Nav items ---

const NAV_ITEMS = [
  { to: "/quarantine", label: "Quarantine", shortLabel: "Quarantine", icon: AlertTriangle },
  { to: "/datalake", label: "Datalake", shortLabel: "Datalake", icon: Database },
  { to: "/search", label: "Search", shortLabel: "Search", icon: Search },
  { to: "/ask", label: "Ask", shortLabel: "Ask", icon: MessageSquare },
  { to: "/review", label: "Review", shortLabel: "Review", icon: FileText },
] as const;

// --- Persona dot ---

function PersonaDot({ id, size = "w-2.5 h-2.5" }: { id: PersonaId; size?: string }) {
  return (
    <span
      className={`${size} rounded-full inline-block flex-shrink-0`}
      style={{ backgroundColor: `hsl(${PERSONAS[id].accent})` }}
    />
  );
}

// --- Persona selector dropdown ---

function PersonaSelector() {
  const { persona, setPersona, config } = usePersona();
  const [open, setOpen] = React.useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex items-center gap-1.5 px-2 py-1 rounded-md text-xs hover:bg-accent/50 transition-colors"
      >
        <PersonaDot id={persona} />
        <span className="font-medium">{config.label}</span>
        <ChevronDown className="h-3 w-3 text-muted-foreground" />
      </button>
      {open && (
        <div className="absolute top-full right-0 mt-1 z-50 bg-card border rounded-lg shadow-lg py-1 min-w-[200px]">
          {PERSONA_IDS.map((id) => {
            const p = PERSONAS[id];
            const active = id === persona;
            return (
              <button
                key={id}
                onClick={() => { setPersona(id); setOpen(false); }}
                className={`w-full text-left px-3 py-1.5 text-xs flex items-center gap-2 hover:bg-accent/50 transition-colors ${
                  active ? "bg-accent/30 font-semibold" : ""
                }`}
              >
                <PersonaDot id={id} />
                <div className="min-w-0">
                  <div className="truncate">{p.label}</div>
                  <div className="text-[10px] text-muted-foreground truncate">{p.focus}</div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// --- TV Layout (10ft) ---

function TvShell() {
  const { persona, config } = usePersona();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const hasStem = searchParams.has("stem");

  // Auto-switch: if ?stem= present, show /review; otherwise show current path (default /datalake)
  const activePath = hasStem ? "/review" : location.pathname;

  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Minimal top bar — large for 10ft viewing */}
      <header className="h-14 border-b bg-card flex items-center px-8 gap-4 flex-shrink-0">
        <PersonaDot id={persona} size="w-4 h-4" />
        <span className="text-xl font-bold text-persona">{config.label}</span>
        <span className="text-lg text-muted-foreground font-medium">
          — {NAV_ITEMS.find((n) => n.to === activePath)?.label ?? "Datalake"}
        </span>
        <div className="flex-1" />
        <TvClock />
      </header>

      {/* Large nav targets — 64px min-height for 10ft touch */}
      <nav className="flex items-center gap-3 px-8 py-2 border-b bg-card/50 flex-shrink-0">
        {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-6 py-3 rounded-lg text-lg font-semibold transition-colors min-h-[64px] ${
                isActive ? "bg-accent text-accent-foreground" : "hover:bg-accent/30 text-muted-foreground"
              }`
            }
          >
            <Icon className="h-6 w-6" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Page content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}

function TvClock() {
  const [time, setTime] = React.useState(() => new Date().toLocaleTimeString());
  React.useEffect(() => {
    const id = setInterval(() => setTime(new Date().toLocaleTimeString()), 1000);
    return () => clearInterval(id);
  }, []);
  return (
    <span className="flex items-center gap-2 text-lg text-muted-foreground">
      <Clock className="h-5 w-5" />
      {time}
    </span>
  );
}

// --- Desktop Layout (5ft) ---

function DeskShell() {
  const { persona } = usePersona();
  const top3 = topDimensions(persona);
  const location = useLocation();
  const isDatalake = location.pathname === "/datalake";

  // Datalake at desk distance = answer canvas (full-height, minimal chrome)
  if (isDatalake) {
    return (
      <div className="flex flex-col h-screen bg-background">
        {/* Minimal top bar — persona dot + nav, no clutter */}
        <header className="h-10 border-b bg-card/80 flex items-center px-4 gap-3 flex-shrink-0">
          <PersonaDot id={persona} size="w-3 h-3" />
          <nav className="flex items-center gap-1">
            {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium transition-colors ${
                    isActive ? "bg-accent text-accent-foreground" : "hover:bg-accent/30 text-muted-foreground"
                  }`
                }
              >
                <Icon className="h-3 w-3" />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="flex-1" />
          <PersonaSelector />
        </header>
        <main className="flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-background">
      <header className="h-12 border-b bg-card flex items-center px-4 gap-3 flex-shrink-0">
        {/* Nav links */}
        <nav className="flex items-center gap-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  isActive ? "bg-accent text-accent-foreground" : "hover:bg-accent/30 text-muted-foreground"
                }`
              }
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="flex-1" />

        {/* Top dimension badges */}
        <div className="hidden lg:flex items-center gap-1">
          {top3.map((dim) => (
            <Badge key={dim} variant="outline" className="text-[9px] px-1.5 py-0 border-persona/30 text-persona">
              {dim.replace(/_/g, " ")}
            </Badge>
          ))}
        </div>

        {/* Persona selector */}
        <PersonaSelector />
      </header>

      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}

// --- Phone Layout (<768px) ---

function PhoneShell() {
  return (
    <div className="flex flex-col h-screen bg-background">
      {/* Compact top bar */}
      <header className="h-10 border-b bg-card flex items-center px-3 gap-2 flex-shrink-0">
        <PhoneTitle />
        <div className="flex-1" />
        <PersonaSelector />
      </header>

      {/* Page content — pb-14 prevents content hiding behind bottom nav */}
      <main className="flex-1 overflow-auto pb-14">
        <Outlet />
      </main>

      {/* Bottom tab nav */}
      <nav className="border-t bg-card flex items-center justify-around safe-bottom flex-shrink-0">
        {NAV_ITEMS.map(({ to, shortLabel, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 py-2 px-2 min-w-[56px] min-h-[44px] text-[10px] transition-colors ${
                isActive ? "text-persona font-semibold" : "text-muted-foreground"
              }`
            }
          >
            <Icon className="h-5 w-5" />
            {shortLabel}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

function PhoneTitle() {
  const location = useLocation();
  const item = NAV_ITEMS.find((n) => n.to === location.pathname);
  const { persona } = usePersona();
  return (
    <div className="flex items-center gap-2">
      <PersonaDot id={persona} />
      <span className="text-sm font-semibold">{item?.label ?? "Embry"}</span>
    </div>
  );
}

// --- Main Shell ---

export default function PersonaShell() {
  const { distance } = usePersona();

  if (distance === "tv") return <TvShell />;
  if (distance === "phone") return <PhoneShell />;
  return <DeskShell />;
}
