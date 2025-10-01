import * as React from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { LoaderDots } from "@/components/ui/loader";

type Hit = { page: number; snippet: string };
type TabKey = "page" | "document" | "chat";

type Props = {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  activeTab: TabKey;
  onTabChange: (t: TabKey) => void;
  query: string;
  onQueryChange: (v: string) => void;
  hits: Hit[];
  indexing: { done: number; total: number };
  onSelectHit: (page: number) => void;
  onAsk: (query: string, scope?: Record<string, unknown>) => void;
};

export default function SearchPanel(props: Props) {
  const { open, onOpenChange, activeTab, onTabChange, query, onQueryChange, hits, indexing, onSelectHit, onAsk } = props;
  const inputRef = React.useRef<HTMLInputElement | null>(null);
  const [messages, setMessages] = React.useState<{ role: "user"|"assistant"; text: string }[]>([]);

  React.useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 0);
  }, [open, activeTab]);

  const sendChat = () => {
    const q = query.trim();
    if (!q) return;
    setMessages((m) => [...m, { role: "user", text: q }]);
    onAsk(q);
    onQueryChange("");
  };

  return (
    <div
      aria-hidden={!open}
      className={[
        "sticky top-0 z-0 -mt-px overflow-hidden border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/80 shadow-sm",
        "transition-all duration-300 ease-out",
        open ? "max-h-96 opacity-100" : "max-h-0 opacity-0 pointer-events-none",
      ].join(" ")}
    >
      <div className="px-3 py-2">
        {/* Tabs */}
        <div className="flex items-center gap-1 text-sm mb-2">
          {(["page","document","chat"] as TabKey[]).map(t => (
            <button
              key={t}
              className={"px-2 py-1 rounded-md " + (activeTab === t ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/60")}
              onClick={() => onTabChange(t)}
            >
              {t === "page" ? "Page" : t === "document" ? "Document" : "Chat"}
            </button>
          ))}
          <div className="ml-auto">
            <Button size="sm" variant="outline" onClick={() => onOpenChange(false)}>Close</Button>
          </div>
        </div>

        {/* Shared query */}
        <div className="flex items-center gap-2">
          <Input
            ref={inputRef}
            placeholder={activeTab === "chat" ? "Ask about this document…" : "Type to search…"}
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                if (activeTab === "chat") sendChat();
                else if (hits.length) onSelectHit(hits[0].page);
              }
              if (e.key === "Escape") onOpenChange(false);
            }}
            className="h-9"
          />
          <Button variant="outline" onClick={() => onQueryChange("") } disabled={!query}>Clear</Button>
          {activeTab === "chat" && (
            <Button onClick={sendChat}>Send</Button>
          )}
        </div>

        {/* Content */}
        {activeTab !== "chat" && (
          <div className="mt-2 border rounded bg-muted/20 max-h-56 overflow-auto">
            {indexing.total > 0 && activeTab === "document" && (
              <div className="px-3 py-2 text-xs text-muted-foreground flex items-center gap-2">
                <LoaderDots /><span>Indexing… {indexing.done}/{indexing.total}</span>
              </div>
            )}
            {hits.length ? (
              <ul>
                {hits.slice(0, 50).map((h, i) => (
                  <li key={`${h.page}-${i}`}>
                    <button
                      className="w-full text-left px-3 py-2 hover:bg-muted text-sm"
                      onClick={() => onSelectHit(h.page)}
                      title={`Go to page ${h.page}`}
                    >
                      <span className="text-muted-foreground mr-2">p{h.page}:</span>
                      <span className="align-middle">{h.snippet || "…"}</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="px-3 py-8 text-sm text-muted-foreground text-center">
                {query ? "No results" : "Type to search the current PDF"}
              </div>
            )}
          </div>
        )}
        {activeTab === "chat" && (
          <div className="mt-2 border rounded bg-muted/20 max-h-56 overflow-auto p-2 space-y-2 text-sm">
            {messages.length === 0 && (
              <div className="text-muted-foreground">Ask a question about the current page or document.</div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={m.role === 'user' ? 'text-right' : ''}>
                <span className={"inline-block px-2 py-1 rounded " + (m.role === 'user' ? 'bg-primary text-primary-foreground' : 'bg-background')}>
                  {m.text}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
