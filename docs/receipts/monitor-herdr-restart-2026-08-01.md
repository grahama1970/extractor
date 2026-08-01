# Monitor Herdr Restart Receipt - 2026-08-01

## Scope

This receipt answers the monitor-herdr restart check for the extractor
workspace after the prior response used `/tmp` proof paths that monitor-herdr
could not find in project files.

## Direct Answers

- Blocked: no.
- Why the agent stopped early: the prior response cited `/tmp` receipts and a
  GitHub issue proof comment, but did not create durable evidence in the
  extractor project tree.
- Immutable goal completed before this receipt: not from monitor-herdr's local
  project-file perspective.
- Brave Search needed: no; no current external fact was required for the local
  ticket and wrapper readback.
- Ask WebGPT/WebKimi needed: no; no reviewer/oracle blocker was present.

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

## Live Wrapper Readback

- Command:
  `EXTRACTOR_ROOT=/home/graham/workspace/experiments/extractor bash /home/graham/workspace/experiments/agent-skills/skills/extractor/run.sh /home/graham/workspace/experiments/extractor/data/input/twins/preset_twin/preset_twin.pdf --out "$OUT/pdf" --offline --format json > "$OUT/result.json"`
- Local result path from restart run:
  `/tmp/extractor-herdr-restart-1122.ZogYpL/result.json`
- Readback:
  - `schema_version`: `extractor.result.v1`
  - `status`: `complete`
  - `source_sha256_len`: `64`
  - `artifact_count`: `2`
  - `offline`: `true`

## Prior Source Proof

- Agent-skills commit:
  `d04bbf8341a0b5eeb345e490db7b4fa306620da8`
- Agent-skills remote `main` readback:
  `d04bbf8341a0b5eeb345e490db7b4fa306620da8`
- Prior proof bundle:
  `/tmp/agent-skills-ticket-1122/proof.md`
- Prior closure results:
  `/tmp/agent-skills-ticket-1122/closure-results.json`
- Prior live e2e readback artifact:
  `/tmp/agent-skills-ticket-1122/e2e-artifact.json`

## Stop Condition

This receipt is the project-local immutable-goal evidence for the restart
check. Any future monitor-herdr restart should first inspect this file, then
rerun the live wrapper command above if fresh runtime proof is required.

mocked: no
live: yes
