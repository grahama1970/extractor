# Immutable Goal Evidence

Immutable Goal: ACHIEVED_WITH_RECEIPT:/home/graham/workspace/experiments/extractor/IMMUTABLE_GOAL.md

## Goal

Resolve the monitor-herdr restart condition for the extractor pane by making the
current immutable-goal evidence discoverable from the extractor project root.

## Project-Root Discovery

The monitor-herdr contract looks upward from the pane cwd for these bounded
project files:

- `IMMUTABLE_GOAL.md`
- `GOAL.md`
- `.goal`
- `.codex/goal.json`
- `.codex/GOAL.md`
- `.tau/goal.json`

This file is the root-level evidence marker for that discovery path.

## Evidence

- Prior extractor project receipt:
  `/home/graham/workspace/experiments/extractor/docs/receipts/monitor-herdr-restart-2026-08-09.md`
- Ticket runtime readback:
  `bash /home/graham/workspace/experiments/agent-skills/skills/ticket/run.sh lookup --repo grahama1970/agent-skills --issue 1122`
- Ticket state:
  `grahama1970/agent-skills#1122` returned `CLOSED`
- Extractor wrapper proof command:
  `bash /home/graham/workspace/experiments/agent-skills/skills/extractor/run.sh /mnt/storage12tb/extractor_data/input/twins/preset_twin/preset_twin.md --out /tmp/extractor-herdr-root-proof-vzjTCV/out --offline --format json`
- Extractor wrapper proof result:
  `/tmp/extractor-herdr-root-proof-vzjTCV/result.json`
- Extractor wrapper readback:
  `schema_version=extractor.result.v1`, `status=complete`, `artifact_count=1`

## Scope

- mocked: no
- live: yes
- This evidence proves the monitor-herdr restart condition has a root
  immutable-goal marker and that the global extractor wrapper still emits the
  canonical JSON contract for one offline local document.
- This evidence does not prove full extractor release readiness, live provider
  enrichment, or all historical GitHub issues.
