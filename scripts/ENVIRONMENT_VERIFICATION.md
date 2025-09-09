# Environment Verification (No Sandbox, Network, DB)

This guide verifies that the Codex CLI agent has full network access, no filesystem sandbox, and working database connectivity to ArangoDB using environment variables.

- approval_policy: `never`
- sandbox_mode: `danger-full-access`
- network_access: `enabled`

## Quick Run

Run the verification script:

```
bash scripts/verify_environment.sh
```

It performs:
- Network check (HTTP 200 from `https://example.com`)
- Filesystem check (read `/etc/os-release`, write `/tmp`)
- ArangoDB check via env vars (`/_api/version` and `/_api/database/user`)

Exit code is non-zero if any check fails.

## Makefile Target

Run the Makefile target:

```
make healthcheck
```

This runs the same script as above.

## GitHub Actions

This repo includes a workflow that starts an ArangoDB service and runs the same checks.

- File: `.github/workflows/env_verification.yml`
- Trigger: manual (`workflow_dispatch`)

From the Actions tab, run “Environment Verification”. It starts ArangoDB with the root password `openSesame` and executes `scripts/verify_environment.sh` with the appropriate environment.

## ArangoDB Environment

Set or confirm the following variables (from `.env` or shell):

```
export ARANGO_HOST=localhost
export ARANGO_PORT=8529
export ARANGO_USERNAME=root
export ARANGO_PASSWORD=openSesame
```

Then run:

```
bash scripts/verify_environment.sh
```

## Sample Output (truncated)

```
== Environment Summary ==
approval_policy: never (session)
sandbox_mode: danger-full-access (session)
network_access: enabled (session)
ARANGO_HOST=localhost ARANGO_PORT=8529

== Network Check ==
[PASS] Internet reachable (example.com, 200)

== Filesystem (No Sandbox) Check ==
[PASS] Can read /etc/os-release
[PASS] Can write to /tmp

== ArangoDB Connectivity (via env) ==
[PASS] GET /_api/version (HTTP 200)
Response: {"server":"arango","license":"community","version":"3.12.4"}
[PASS] GET /_api/database/user (HTTP 200)
Databases (truncated): {"error":false,"code":200,"result":["_system", ...]

All checks passed. Full network, DB connectivity, and no sandbox confirmed.
```

## Notes
- The script is non-destructive: it only reads server version and user databases.
- If ArangoDB is remote, ensure host/port and firewall rules allow access.
- If using Docker, expose `8529` and map to `localhost`.
- You can override env vars inline: `ARANGO_PASSWORD=... bash scripts/verify_environment.sh`.
