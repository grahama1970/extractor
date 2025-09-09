# Agent + Human Debugging Guide (tools/gold_annotator_2)

This repo supports two complementary debugging paths:

- Agent (automation/logs): Puppeteer + CDP capture (no UI)
- Human (live UI): Chrome DevTools attached to the Ubuntu Chromium instance via VS Code port forwarding

The goal is minimal friction, zero guesswork, and no fragile shared browsers.

---

## TL;DR

- Use VS Code Remote-SSH. Forward the app (3012) and CDP (9222) ports.
- Start the app + Chromium headless RD on Ubuntu (one command/task).
- Attach DevTools on your Mac to the forwarded CDP port (chrome://inspect).
- Agents capture logs/screenshots with Puppeteer + CDP (optional artifact path).

---

## Why this design

- Puppeteer is not “blind.” It already talks to Chromium via CDP. It can capture console logs, page errors, network failures, and even raw CDP domains (Runtime/Log/Network/DOM/Performance) without any external forwarding.
- The human needs a live **DevTools UI** to inspect React/Tailwind/Shadcn (Elements/Sources/Performance). That’s why we expose the DevTools Protocol port (9222) to the Mac via VS Code port forwarding.
- No Kasm/VNC or proxies required. VS Code does the port forwarding; Chromium runs headless with RD on localhost.

---

## Recommended flow (human + agent)

1) Start app + Chromium headless RD (Ubuntu)

- Option A (Task):
  - VS Code → Cmd/Ctrl+Shift+P → “Tasks: Run Task” → Start Ubuntu Dev (app+RD)
- Option B (Script):
  - `scripts/ubuntu_dev.sh` (one command, launches both)
- What it does:
  - App: `http://127.0.0.1:3012`
  - DevTools (CDP): `http://127.0.0.1:9222`

2) Forward ports (VS Code → Ports View)

- VS Code will auto‑detect and forward 3012 + 9222 (see .vscode/settings.json)
- If needed, manually forward:
  - App: 3012 → localhost:3012 (Mac)
  - CDP: 9222 → localhost:9222 (Mac)

3) Attach DevTools (Mac)

- Open Chrome → `chrome://inspect`
- Configure… → add `localhost:9222`
- Click “Inspect” on the remote tab (“Gold Annotator 2”)

4) (Optional) Agent artifacts via Puppeteer + CDP

- Run the capture task/script to write:
  - JSONL console logs + errors + request failures
  - initial full-page screenshot

---

## Files provided

- `.vscode/settings.json`
  - Auto‑forwards process ports
  - Labels 3012 as “gold‑annotator (app)”, 9222 as “chromium‑cdp”
- `.vscode/tasks.json`
  - Task: “Start Ubuntu Dev (app+RD)” → runs `scripts/ubuntu_dev.sh`
- `.vscode/launch.json`
  - VS Code debugger attach to forwarded CDP on localhost:9222
- `scripts/ubuntu_dev.sh`
  - Starts Next dev @ 127.0.0.1:3012
  - Starts Chromium headless RD @ 127.0.0.1:9222 (opens the app)
  - Prints quick status and log paths
- `tools/gold_annotator_2/scripts/cdp_capture.mjs` (optional)
  - Connect over CDP to browserless and record console logs + screenshot

---

## Do we “need” scripts/ubuntu_dev.sh?

- Not strictly. VS Code **forwards** ports, but it does **not** launch Chromium for you. Something must start:
  - the app (Next dev server), and
  - a Chromium instance with `--remote-debugging-port=9222`.
- You can:
  - keep `scripts/ubuntu_dev.sh` (single command convenience), or
  - inline the same commands in a VS Code task, or
  - run the two commands manually.
- The script exists to avoid typos and to print a quick “OK” status.

Minimal commands (manual alternative):

```bash
# App
cd ~/workspace/experiments/extractor/tools/gold_annotator_2
npm i
cp node_modules/pdfjs-dist/build/pdf.worker.min.mjs public/pdf.worker.min.js
npm run dev -- -H 127.0.0.1 -p 3012

# Chromium headless RD
pkill -f 'remote-debugging.*9222' || true
CHROME_BIN=$(command -v chromium || command -v chromium-browser || command -v google-chrome)
"$CHROME_BIN" --headless=new   --remote-debugging-address=127.0.0.1   --remote-debugging-port=9222   --user-data-dir=/tmp/chrome-rd   'http://127.0.0.1:3012' >/tmp/chrome.log 2>&1 &
```

---

## Agent diagnostics (Puppeteer + CDP)

Key point: the agent does **not** need external port forwarding for telemetry.

- Listen to high‑level events:

```js
page.on('console', m => console.log(`[console:${m.type()}]`, m.text()));
page.on('pageerror', e => console.error('[pageerror]', e));
page.on('requestfailed', r => console.warn('[requestfailed]', r.url(), r.failure()?.errorText));
page.on('response', async res => {
  if (res.status() >= 400) console.warn('[response>=400]', res.status(), res.url());
});
```

- Drop to raw CDP when needed:

```js
const client = await page.target().createCDPSession();
await client.send('Runtime.enable');
await client.send('Log.enable');
await client.send('Network.enable');
client.on('Log.entryAdded', e => console.log('[Log.entry]', e.entry.level, e.entry.text));
client.on('Runtime.exceptionThrown', e => console.error('[Runtime.exception]', e.exceptionDetails?.text || e));
client.on('Network.loadingFailed', e => console.warn('[Network.loadingFailed]', e.errorText, e.requestId));
```

- For artifacts without UI, connect to browserless (already running) using `tools/gold_annotator_2/scripts/cdp_capture.mjs`.

---

## Smoke tests

Ubuntu:

```bash
# App
curl -sI http://127.0.0.1:3012 | head -n1   # HTTP/1.1 200 OK
# CDP version / targets
curl -s http://127.0.0.1:9222/json/version | head
curl -s http://127.0.0.1:9222/json/list | head
```

Mac (after VS Code forwards):

```bash
curl -sI http://localhost:3012 | head -n1
curl -s http://localhost:9222/json/list | head
# DevTools: chrome://inspect → add localhost:9222 → Inspect
```

---

## What we’re not doing anymore

- No Kasm/noVNC, no reverse proxies just to get a browser. VS Code forwarding + headless RD is a simpler, safer path.
- No reliance on “host.docker.internal” in Linux containers for core debugging; we use loopback + VS Code forwards.

---

## FAQ

- “Can VS Code launch Chromium for me?”
  - Not on the remote host; it forwards ports for existing processes. We launch Chromium headless RD ourselves.
- “Can I debug only with Puppeteer?”
  - For logs/screenshots/traces: yes. For interactive DOM/CSS/breakpoints: use DevTools.
- “Why headless?”
  - Many remote sessions have no DISPLAY/X server; headless avoids that. DevTools Protocol still works.

---

## Keep it minimal

- Human UI: VS Code tasks + port forwarding + Chrome DevTools.
- Agent diagnostics: Puppeteer + CDP events (optionally browserless for artifacts).
- One script (or task) on Ubuntu to start the app + RD; everything else is standard.
