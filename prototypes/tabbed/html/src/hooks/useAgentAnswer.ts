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
import type { ManipulationCommand } from "@/lib/d3-manipulate";

// --- Types ---

export type AnswerPayloadType = "image" | "html" | "data" | "table" | "text";

export type AnswerPayload = {
  type: AnswerPayloadType;
  title?: string;
  content: string;
  summary?: string;
  source?: string;
  vizFamily?: string;  // hint for manipulation routing
};

export type AgentStatus = "idle" | "listening" | "thinking" | "rendering" | "manipulating";

export type AgentState = {
  answer: AnswerPayload | null;
  status: AgentStatus;
  error: string | null;
  transcript: string | null;
};

const AGENT_API = import.meta.env.VITE_AGENT_API ?? "http://127.0.0.1:8003";

// --- SSE streaming ---

type StreamResult = {
  answer: AnswerPayload | null;
  manipulations: ManipulationCommand[] | null;
};

async function askStream(
  query: string,
  persona: string,
  onStatus: (status: AgentStatus) => void,
  onManipulate: (commands: ManipulationCommand[]) => void,
  signal: AbortSignal,
): Promise<StreamResult> {
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
  let manipulations: ManipulationCommand[] | null = null;

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
              manipulating: "manipulating",
            };
            onStatus(map[data.status] ?? "thinking");
          } else if (currentEvent === "answer") {
            answer = data as AnswerPayload;
          } else if (currentEvent === "manipulate") {
            // D3 manipulation commands — forward to active iframe
            manipulations = data.commands as ManipulationCommand[];
            onManipulate(manipulations);
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

  if (!answer && !manipulations) throw new Error("No answer received");
  return { answer, manipulations };
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
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const iframeOriginRef = useRef<string | null>(null);
  const pendingManipulationsRef = useRef<ManipulationCommand[]>([]);
  const answerRef = useRef<AnswerPayload | null>(null);

  // Keep answerRef in sync with state
  answerRef.current = state.answer;

  // Forward manipulation commands to the active iframe
  const forwardToIframe = useCallback((commands: ManipulationCommand[]) => {
    const iframe = iframeRef.current;
    const origin = iframeOriginRef.current ?? "*";
    if (iframe?.contentWindow) {
      iframe.contentWindow.postMessage(
        { type: "d3-manipulate", commands, vizFamily: answerRef.current?.vizFamily },
        origin,
      );
    } else {
      // Queue for when iframe becomes available (cap at 100 to prevent unbounded growth)
      if (pendingManipulationsRef.current.length < 100) {
        pendingManipulationsRef.current.push(...commands);
      }
    }
  }, []);

  const ask = useCallback(async (query: string) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    // Read from ref to avoid stale closure over state.answer
    const currentAnswer = answerRef.current;
    const hasActiveViz = currentAnswer?.type === "html" || currentAnswer?.type === "data";

    setState((s) => ({
      ...s,
      answer: hasActiveViz ? s.answer : null,
      status: "thinking",
      error: null,
      transcript: query,
    }));

    try {
      const result = await askStream(
        query, persona,
        (status) => setState((s) => ({ ...s, status })),
        (commands) => forwardToIframe(commands),
        controller.signal,
      );

      if (result.manipulations && !result.answer) {
        setState((s) => ({ ...s, status: "idle", transcript: query }));
      } else if (result.answer) {
        // Clear pending manipulations when replacing the visualization
        pendingManipulationsRef.current.length = 0;
        setState({ answer: result.answer, status: "rendering", error: null, transcript: query });
        setTimeout(() => {
          setState((s) => (s.status === "rendering" ? { ...s, status: "idle" } : s));
        }, 800);

        if (result.answer.summary) speakSummary(result.answer.summary, controller.signal);
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setState((prev) => ({
        answer: hasActiveViz ? prev.answer : null,
        status: "idle",
        error: err instanceof Error ? err.message : "Unknown error",
        transcript: query,
      }));
    }
  }, [persona, forwardToIframe]);

  const clear = useCallback(() => {
    abortRef.current?.abort();
    mediaRecorderRef.current?.stop();
    pendingManipulationsRef.current.length = 0;
    // Flush session to /episodic-archiver before clearing
    fetch(`${AGENT_API}/api/agent/session/flush`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: "", persona }),
    }).catch(() => {}); // non-blocking
    setState({ answer: null, status: "idle", error: null, transcript: null });
  }, [persona]);

  // Record audio → VAD silence detection → Whisper transcribe → ask
  const listen = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const VAD_SILENCE_THRESHOLD = 0.01; // RMS below this = silence
    const VAD_SILENCE_MS = 1500;        // Stop after 1.5s of silence
    const VAD_MAX_DURATION_MS = 8000;   // Hard max recording time
    const VAD_MIN_DURATION_MS = 500;    // Don't stop before 0.5s

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
          chunks.length = 0; // Release blob references
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

      // --- VAD: Web Audio API silence detection ---
      let audioCtx: AudioContext | null = null;
      try {
        audioCtx = new AudioContext();
        const source = audioCtx.createMediaStreamSource(stream);
        const analyser = audioCtx.createAnalyser();
        analyser.fftSize = 512;
        source.connect(analyser);

        const dataArray = new Float32Array(analyser.fftSize);
        const startTime = Date.now();
        let lastSpeechTime = Date.now();
        let hasSpeech = false;

        const checkSilence = () => {
          if (recorder.state !== "recording" || controller.signal.aborted) {
            audioCtx?.close();
            return;
          }

          const elapsed = Date.now() - startTime;

          // Hard max duration
          if (elapsed > VAD_MAX_DURATION_MS) {
            audioCtx?.close();
            if (recorder.state === "recording") recorder.stop();
            return;
          }

          // Compute RMS amplitude
          analyser.getFloatTimeDomainData(dataArray);
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i] * dataArray[i];
          }
          const rms = Math.sqrt(sum / dataArray.length);

          if (rms > VAD_SILENCE_THRESHOLD) {
            lastSpeechTime = Date.now();
            hasSpeech = true;
          }

          // Stop after sustained silence (only if we've heard speech and passed min duration)
          const silenceDuration = Date.now() - lastSpeechTime;
          if (hasSpeech && elapsed > VAD_MIN_DURATION_MS && silenceDuration > VAD_SILENCE_MS) {
            audioCtx?.close();
            if (recorder.state === "recording") recorder.stop();
            return;
          }

          requestAnimationFrame(checkSilence);
        };

        requestAnimationFrame(checkSilence);
      } catch {
        // AudioContext not available — fall back to fixed timeout
        audioCtx?.close();
        setTimeout(() => {
          if (recorder.state === "recording") recorder.stop();
        }, 5000);
      }
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
      if (e.code === "Space" && state.status === "idle") {
        const el = e.target as HTMLElement;
        const tag = el?.tagName;
        const isInteractive = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT"
          || tag === "BUTTON" || tag === "A"
          || el?.isContentEditable
          || el?.getAttribute("role") === "button";
        if (!isInteractive) {
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

  // Register iframe ref for manipulation forwarding
  const setIframeRef = useCallback((el: HTMLIFrameElement | null) => {
    iframeRef.current = el;
    // Capture iframe origin for postMessage targeting
    try {
      iframeOriginRef.current = el?.src ? new URL(el.src, window.location.href).origin : null;
    } catch {
      iframeOriginRef.current = null;
    }
    // Flush any pending manipulations
    if (el?.contentWindow && pendingManipulationsRef.current.length > 0) {
      const pending = pendingManipulationsRef.current.splice(0);
      const origin = iframeOriginRef.current ?? "*";
      el.contentWindow.postMessage(
        { type: "d3-manipulate", commands: pending, vizFamily: answerRef.current?.vizFamily },
        origin,
      );
    }
  }, []);

  // Check for speech availability
  const speechAvailable = typeof navigator !== "undefined"
    && typeof navigator.mediaDevices !== "undefined"
    && typeof navigator.mediaDevices.getUserMedia === "function";

  return { ...state, ask, clear, listen, setIframeRef, speechAvailable };
}
