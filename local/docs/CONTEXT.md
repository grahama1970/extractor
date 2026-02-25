# CONTEXT.md - Extractor Project Handoff

**Last Updated**: 2026-02-25
**Session Focus**: 5ft Voice Canvas complete, curated skills, cleanup + push
**Primary Working Repo**: `/home/graham/workspace/experiments/extractor` (pipeline code)
**Companion Repo**: `/home/graham/workspace/experiments/pi-mono` (skills)

---

## Current State

### Git: Clean (pushed to main)
- `375c5c53` chore: cleanup 538 stale files
- `229d98e7` feat: pipeline S00-S14 improvements
- `7561be49` feat: 5ft voice canvas + curated skills
- `8d582d4a` feat: new pipeline steps, providers, tests
- `7dc5ea60` chore: remaining docs, scripts, data

### Pipeline Quality (350 verdicts)
334 PASS (95.4%), 14 WARN (4.0%), 2 FAIL (0.6%). Average ~0.94.
Score trajectory: 0.659 → 0.718 → 0.784 → 0.843 → 0.945 → 0.960.

### 5ft Voice-Activated Answer Canvas — COMPLETE
- **SSE streaming**: `POST /api/agent/ask-stream` with status events
- **PersonaPlex voice**: Whisper STT (port 2022) + Kokoro TTS (port 8880)
- **Backend proxies**: `/voice/transcribe`, `/voice/speak` in agent_endpoint.py
- **Frontend**: useAgentAnswer.ts (MediaRecorder → Whisper → SSE → Kokoro)
- **Canvas UX**: AnswerCanvas.tsx with Idle/Listening/Thinking/Rendering states
- **D3**: D3ResponsiveChart.tsx (13 chart types, 18px+ fonts, distance-aware)
- **Build**: Clean (tsc + bun run build)

### Canvas-Intent Classifier — SHADOW MODE
- **6 classes**: VISUALIZE, QUERY, SEARCH, COMPARE, NAVIGATE, EXPLAIN
- **Model**: TF-IDF + LogReg, 60 seed labels, CV=53%
- **Registry**: `canvas-intent` in model_registry.json (shadow_mode=true)
- **Cascade**: classify_intent() tries Tier 0.5 classifier → falls back to regex heuristic
- **Shadow logging**: Disagreements logged to ~/.pi/assistant/shadow.jsonl
- **Needs**: Real voice queries to improve (53% CV is seed-only)

### Curated Skills — DEPLOYED
- `.claude/skills/` is a real directory with 30 individual symlinks (not blanket 200+)
- `scripts/curate_skills.sh` for rebuilding
- `skills-broadcast` amended: `is_curated_skills_dir()` preserves curated dirs on `link`
- Reduces Claude Code context overhead by ~90% per tool response

### Shadow-LEGO (Prior Session)
- Shadow S00 classifier deployed (GradientBoosting, 724 samples)
- S05 integration: `SHADOW_S00=true` in .env
- Co-evolutionary feedback loop wired into inline_reviewer.py

---

## Key Files

| File | Purpose |
|------|---------|
| `prototypes/tabbed/api/agent_endpoint.py` | Canvas API: SSE, voice, intent routing |
| `prototypes/tabbed/html/src/hooks/useAgentAnswer.ts` | PersonaPlex voice hook |
| `prototypes/tabbed/html/src/components/AnswerCanvas.tsx` | Canvas voice UX |
| `prototypes/tabbed/html/src/components/d3/D3ResponsiveChart.tsx` | 13-chart D3 dispatch |
| `src/extractor/pipeline/steps/s05_table_extractor.py` | Shadow S00 + stream fallback |
| `scripts/curate_skills.sh` | Project skill filtering |
| `pi-mono/.pi/skills/skills-broadcast/run.sh` | Curated dir preservation |
| `pi-mono/.pi/skills/assistant/model_registry.json` | canvas-intent registration |
| `pi-mono/.pi/skills/assistant/train_classifiers.py` | canvas-intent training |

---

## Next Steps

1. **Shadow label collection** — canvas-intent at 53% CV needs real voice queries (non-trivial)
2. **Code-split** — 543KB index chunk in canvas build needs lazy imports
3. **CONTEXT.md in pi-mono** — update companion repo context
4. **Switch to Pi** — user considering moving from Claude Code
5. **Monitor Shadow S00** — verify stream prioritization improves table_fidelity
