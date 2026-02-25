/**
 * AnswerCanvas — display-only answer surface for 5ft (desk) viewing.
 *
 * No UI controls. Shows whatever the agent produces. Users speak voice
 * commands (Web Speech API → SSE → agent → canvas), the system classifies
 * intent and displays the answer. Kokoro TTS speaks the summary aloud.
 *
 * Activation:
 *   - Space bar (idle) → start listening
 *   - Ctrl+Shift+A → keyboard fallback
 *   - Escape → clear canvas
 */
import React, { useMemo } from "react";
import { usePersona } from "@/contexts/PersonaContext";
import { PERSONAS } from "@/lib/persona-config";
import { useAgentAnswer, type AnswerPayload, type AgentStatus } from "@/hooks/useAgentAnswer";
import D3ResponsiveChart, { type ChartDataPoint } from "@/components/d3/D3ResponsiveChart";
import D3Table from "@/components/d3/D3Table";

// --- Idle State ---

function IdleState({ accentHsl }: { accentHsl: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 animate-fade-in-5ft">
      {/* Persona dot with breathing animation */}
      <div
        className="w-16 h-16 rounded-full animate-breathe"
        style={{ backgroundColor: `hsl(${accentHsl})`, opacity: 0.7 }}
      />
      <p className="text-2xl text-muted-foreground font-light tracking-wide">
        Ask me anything
      </p>
      <p className="text-sm text-muted-foreground/50">
        Press Space to speak
      </p>
    </div>
  );
}

// --- Listening State ---

function ListeningState({ accentHsl }: { accentHsl: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-6 animate-fade-in-5ft">
      {/* Pulsing ring around persona dot indicates active listening */}
      <div className="relative">
        <div
          className="w-20 h-20 rounded-full animate-pulse"
          style={{
            backgroundColor: `hsl(${accentHsl})`,
            opacity: 0.9,
            boxShadow: `0 0 0 8px hsl(${accentHsl} / 0.2), 0 0 0 16px hsl(${accentHsl} / 0.1)`,
          }}
        />
      </div>
      <p className="text-2xl text-foreground font-medium tracking-wide">
        Listening...
      </p>
      <p className="text-sm text-muted-foreground/60">
        Speak your question
      </p>
    </div>
  );
}

// --- Status Indicator ---

function StatusIndicator({ status, transcript }: { status: AgentStatus; transcript: string | null }) {
  if (status === "idle" || status === "listening") return null;

  const labels: Record<AgentStatus, string> = {
    idle: "",
    listening: "",
    thinking: "Thinking...",
    rendering: "Rendering...",
  };

  return (
    <div className="absolute bottom-6 right-6 flex flex-col items-end gap-1 animate-fade-in-5ft">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <div className="w-2 h-2 rounded-full bg-persona animate-pulse" />
        <span>{labels[status]}</span>
      </div>
      {transcript && status === "thinking" && (
        <p className="text-xs text-muted-foreground/50 max-w-xs truncate">
          &ldquo;{transcript}&rdquo;
        </p>
      )}
    </div>
  );
}

// --- Error Display ---

function ErrorDisplay({ error, onDismiss }: { error: string; onDismiss: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center h-full gap-4 animate-fade-in-5ft">
      <p className="text-xl text-destructive font-medium">Something went wrong</p>
      <p className="text-lg text-muted-foreground max-w-lg text-center">{error}</p>
      <button
        onClick={onDismiss}
        className="text-sm text-muted-foreground underline hover:text-foreground transition-colors"
      >
        Dismiss
      </button>
    </div>
  );
}

// --- Content Renderers ---

function ImageContent({ answer }: { answer: AnswerPayload }) {
  return (
    <div className="flex flex-col items-center justify-center h-full p-8 gap-4 animate-fade-in-5ft">
      {answer.title && (
        <h1 className="text-2xl font-bold text-persona">{answer.title}</h1>
      )}
      <img
        src={answer.content}
        alt={answer.title || "Answer"}
        className="max-w-full max-h-[80vh] object-contain rounded-lg"
      />
      {answer.source && (
        <p className="text-sm text-muted-foreground">{answer.source}</p>
      )}
    </div>
  );
}

function HtmlContent({ answer }: { answer: AnswerPayload }) {
  return (
    <div className="w-full h-full animate-fade-in-5ft">
      {answer.title && (
        <h1 className="text-2xl font-bold text-persona px-8 pt-6">{answer.title}</h1>
      )}
      <iframe
        srcDoc={answer.content}
        className="w-full flex-1 border-0"
        style={{ height: "calc(100% - 60px)" }}
        sandbox="allow-scripts allow-same-origin"
        title={answer.title || "Answer"}
      />
    </div>
  );
}

function DataContent({ answer, accentHsl }: { answer: AnswerPayload; accentHsl: string }) {
  const parsed = useMemo(() => {
    try {
      return JSON.parse(answer.content);
    } catch {
      return null;
    }
  }, [answer.content]);

  if (!parsed) {
    return <TextContent answer={answer} />;
  }

  // If parsed is an array of objects with label/value, render as chart
  if (Array.isArray(parsed) && parsed.length > 0 && "label" in parsed[0] && "value" in parsed[0]) {
    return (
      <div className="w-full h-full p-8 animate-fade-in-5ft">
        <D3ResponsiveChart
          data={parsed as ChartDataPoint[]}
          chartType={parsed.length > 10 ? "line" : "bar"}
          accentHsl={accentHsl}
          title={answer.title}
        />
      </div>
    );
  }

  // If it's an array of objects, render as table
  if (Array.isArray(parsed) && parsed.length > 0 && typeof parsed[0] === "object") {
    return <D3Table data={parsed} accentHsl={accentHsl} title={answer.title} />;
  }

  // Fallback: render as formatted JSON text
  return (
    <TextContent
      answer={{ ...answer, content: JSON.stringify(parsed, null, 2) }}
    />
  );
}

function TableContent({ answer, accentHsl }: { answer: AnswerPayload; accentHsl: string }) {
  const parsed = useMemo(() => {
    try {
      return JSON.parse(answer.content);
    } catch {
      return null;
    }
  }, [answer.content]);

  if (!parsed || !Array.isArray(parsed)) {
    return <TextContent answer={answer} />;
  }

  return <D3Table data={parsed} accentHsl={accentHsl} title={answer.title} />;
}

function TextContent({ answer }: { answer: AnswerPayload }) {
  return (
    <div className="flex flex-col items-center justify-center h-full p-12 animate-fade-in-5ft">
      {answer.title && (
        <h1 className="text-3xl font-bold text-persona mb-6">{answer.title}</h1>
      )}
      <div className="max-w-3xl text-xl leading-relaxed text-foreground whitespace-pre-wrap">
        {answer.content}
      </div>
      {answer.source && (
        <p className="mt-6 text-sm text-muted-foreground">{answer.source}</p>
      )}
    </div>
  );
}

// --- Main Canvas ---

export default function AnswerCanvas() {
  const { persona } = usePersona();
  const config = PERSONAS[persona];
  const { answer, status, error, transcript, clear, speechAvailable } = useAgentAnswer(persona);

  const accentHsl = config.accent;

  return (
    <div className="relative w-full h-full bg-background overflow-hidden">
      {/* Content area */}
      {error ? (
        <ErrorDisplay error={error} onDismiss={clear} />
      ) : status === "listening" ? (
        <ListeningState accentHsl={accentHsl} />
      ) : !answer ? (
        <IdleState accentHsl={accentHsl} speechAvailable={speechAvailable} />
      ) : answer.type === "image" ? (
        <ImageContent answer={answer} />
      ) : answer.type === "html" ? (
        <HtmlContent answer={answer} />
      ) : answer.type === "data" ? (
        <DataContent answer={answer} accentHsl={accentHsl} />
      ) : answer.type === "table" ? (
        <TableContent answer={answer} accentHsl={accentHsl} />
      ) : (
        <TextContent answer={answer} />
      )}

      {/* Status indicator — bottom-right, subtle */}
      <StatusIndicator status={status} transcript={transcript} />
    </div>
  );
}
