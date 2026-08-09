# Monitor Herdr Restart Receipt - 2026-08-09

Immutable Goal: ACHIEVED_WITH_RECEIPT:/home/graham/workspace/experiments/extractor/docs/receipts/monitor-herdr-restart-2026-08-09.md

## Restart Input

- Herdr pane: `w11:p17`
- Agent: `codex`
- Cwd: `/home/graham/workspace/experiments/extractor`
- Monitor reason: `stopped_status:done, transcript_goal:unmet`
- Monitor finding: immutable goal evidence was not found in project files.

## Direct Answers

- Blocked: no.
- Why the prior stop was early: the existing project receipt documented the
  ticket and wrapper proof but did not include the literal machine-readable
  `Immutable Goal:` line that monitor-herdr classifies.
- Immutable goal completed now: yes, with this in-project receipt and the
  command readbacks below.
- Brave Search needed: no; no current external fact or documentation lookup was
  needed to resolve a local receipt-classification failure.
- Ask WebGPT/WebKimi needed: no; no reviewer/oracle blocker was present.

## Memory-First Hook

- Hook file:
  `/home/graham/.codex/hook-logs/memory-first-20260809T125012Z.json`
- Top match:
  `What is _invoke_prompt_reviewer_subagent in monitor_sparta.py?`
- Applicability: not applicable to this extractor receipt restart; it concerns
  a `monitor_sparta.py` symbol, not monitor-herdr project receipt discovery.

## Ticket Check

- Runtime used: `$ticket`
- Command:
  `bash /home/graham/workspace/experiments/agent-skills/skills/ticket/run.sh lookup --issue 1122 --repo grahama1970/agent-skills`
- Issue: `grahama1970/agent-skills#1122`
- Title: `Repair extractor skill wrapper and current-state docs`
- State readback: `CLOSED`
- State reason: `COMPLETED`
- Closed at: `2026-07-30T22:02:34Z`
- Proof comment:
  `https://github.com/grahama1970/agent-skills/issues/1122#issuecomment-5136722174`

## Live Wrapper Proof

- Command:
  `EXTRACTOR_ROOT=/home/graham/workspace/experiments/extractor bash /home/graham/workspace/experiments/agent-skills/skills/extractor/run.sh /home/graham/workspace/experiments/extractor/data/input/twins/preset_twin/preset_twin.pdf --out "$OUT/pdf" --offline --format json > "$OUT/result.json"`
- Local result path:
  `/tmp/extractor-herdr-restart-20260809.71QuO7/result.json`
- Readback:
  - `schema_version`: `extractor.result.v1`
  - `status`: `complete`
  - `source_sha256_len`: `64`
  - `artifact_count`: `2`
  - `offline`: `true`

## Stop Condition

Monitor-herdr can treat this restart as resolved when the current response
names this file as the receipt and the file exists inside the extractor project
boundary.

mocked: no
live: yes
