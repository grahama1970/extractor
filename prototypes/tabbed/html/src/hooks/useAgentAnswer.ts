/**
 * useAgentAnswer — PersonaPlex voice-activated agent hook for 5ft canvas.
 *
 * Single voice system: Whisper STT + Kokoro TTS via backend proxy.
 *   STT: MediaRecorder → /api/agent/voice/transcribe → Whisper (port 2022)
 *   Agent: transcript → /api/agent/ask-stream (SSE) → AnswerPayload
 *   TTS: summary → /api/agent/voice/speak → Kokoro (port 8880) → audio
 *
 * Keyboard fallback: Ctrl+Shift+A for typing when mic unavailable.
 */
import { useCallback, useEffect, useRef, useState } from "react";

// --- Types ---

export type AnswerPayloadType = "image" | "html" | "data" | "table" | "text";

export type AnswerPayload = {
  type: AnswerPayloadType;
  title?: string;
  content: string;
  summary?: string;
  source?: string;
};

export type AgentStatus = "idle" | "listening" | "thinking" | "rendering";

export type AgentState = {
  answer: AnswerPayload | null;
  status: AgentStatus;
  error: string | null;
  transcript: string | null;
};

const AGENT_API = import.meta.env.VITE_AGENT_API ?? "http://127.0.0.1:8003";

// --- SSE streaming ---

async function askStream(
  query: string,
  persona: string,
  onStatus: (status: AgentStatus) => void,
  signal: AbortSignal,
): Promise<AnswerPayload> {
  const res = await fetch(`${AGENT_API}/api/agent/ask-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, persona }),
    signal,
  });

  if (!res.ok) {
    throw new Error(`Agent error ${res.status}: ${await res.text()}`);
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");

  const decoder = new TextDecoder();
  let buffer = "";
  let answer: AnswerPayload | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    let currentEvent = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith("data: ") && currentEvent) {
        try {
          const data = JSON.parse(line.slice(6));
          if (currentEvent === "status") {
            const map: Record<string, AgentStatus> = {
              classifying: "thinking",
              searching: "thinking",
              rendering: "rendering",
            };
            onStatus(map[data.status] ?? "thinking");
          } else if (currentEvent === "answer") {
            answer = data as AnswerPayload;
          } else if (currentEvent === "error") {
            throw new Error(data.message);
          }
        } catch (e) {
          if (e instanceof SyntaxError) continue;
          throw e;
        }
        currentEvent = "";
      }
    }
  }

  if (!answer) throw new Error("No answer received");
  return answer;
}

// --- Whisper STT via backend proxy ---

async function transcribeAudio(blob: Blob, signal: AbortSignal): Promise<string> {
  const res = await fetch(`${AGENT_API}/api/agent/voice/transcribe`, {
    method: "POST",
    headers: { "Content-Type": blob.type || "audio/webm" },
    body: blob,
    signal,
  });
  if (!res.ok) throw new Error("Transcription failed");
  const data = await res.json();
  if (data.error) throw new Error(data.error);
  return data.text || "";
}

// --- Kokoro TTS via backend proxy ---

async function speakSummary(text: string, signal: AbortSignal): Promise<void> {
  try {
    const res = await fetch(`${AGENT_API}/api/agent/voice/speak`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, voice: "af_sky", speed: 1.0 }),
      signal,
    });
    if (!res.ok) return;

    const blob = await res.blob();
    if (blob.size === 0 || signal.aborted) return;

    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    audio.addEventListener("ended", () => URL.revokeObjectURL(url));
    audio.addEventListener("error", () => URL.revokeObjectURL(url));

    if (!signal.aborted) {
      await audio.play().catch(() => {});
    }
  } catch {
    // TTS failure is non-fatal
  }
}

// --- Main hook ---

export function useAgentAnswer(persona: string) {
  const [state, setState] = useState<AgentState>({
    answer: null,
    status: "idle",
    error: null,
    transcript: null,
  });

  const abortRef = useRef<AbortController | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);

  const ask = useCallback(async (query: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setState({ answer: null, status: "thinking", error: null, transcript: query });

    try {
      const answer = await askStream(
        query, persona,
        (status) => setState((s) => ({ ...s, status })),
        controller.signal,
      );

      setState({ answer, status: "rendering", error: null, transcript: query });
      setTimeout(() => {
        setState((s) => (s.status === "rendering" ? { ...s, status: "idle" } : s));
      }, 800);

      if (answer.summary) speakSummary(answer.summary, controller.signal);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setState({
        answer: null, status: "idle",
        error: err instanceof Error ? err.message : "Unknown error",
        transcript: query,
      });
    }
  }, [persona]);

  const clear = useCallback(() => {
    abortRef.current?.abort();
    mediaRecorderRef.current?.stop();
    setState({ answer: null, status: "idle", error: null, transcript: null });
  }, []);

  // Record audio → Whisper transcribe → ask
  const listen = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
      mediaRecorderRef.current = recorder;
      const chunks: Blob[] = [];

      setState((s) => ({ ...s, status: "listening", error: null }));

      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };

      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        if (controller.signal.aborted || chunks.length === 0) {
          setState((s) => (s.status === "listening" ? { ...s, status: "idle" } : s));
          return;
        }

        const blob = new Blob(chunks, { type: "audio/webm" });
        setState((s) => ({ ...s, status: "thinking", transcript: "Transcribing..." }));

        try {
          const text = await transcribeAudio(blob, controller.signal);
          if (text.trim()) {
            ask(text.trim());
          } else {
            setState((s) => ({ ...s, status: "idle", transcript: null }));
          }
        } catch {
          setState((s) => ({ ...s, status: "idle", error: "Transcription failed" }));
        }
      };

      recorder.start();

      // Stop recording after silence or max duration (5s)
      setTimeout(() => {
        if (recorder.state === "recording") recorder.stop();
      }, 5000);
    } catch {
      // Mic permission denied — fall back to keyboard
      const query = window.prompt("Ask the canvas:");
      if (query?.trim()) ask(query.trim());
      else setState((s) => ({ ...s, status: "idle" }));
    }
  }, [ask]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.ctrlKey && e.shiftKey && e.key === "A") {
        e.preventDefault();
        const query = window.prompt("Ask the canvas:");
        if (query?.trim()) ask(query.trim());
      }
      if (e.code === "Space" && state.status === "idle" && !state.answer) {
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag !== "INPUT" && tag !== "TEXTAREA" && tag !== "SELECT") {
          e.preventDefault();
          listen();
        }
      }
      if (e.key === "Escape" && (state.answer || state.error)) {
        clear();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [ask, clear, listen, state.answer, state.status, state.error]);

  return { ...state, ask, clear, listen };
}
