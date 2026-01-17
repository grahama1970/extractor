import fs from 'node:fs';
import { spawn } from 'node:child_process';

const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';
const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080/main';

async function getWS() {
  try {
    const res = await fetch(DISCOVERY);
    const j = await res.json();
    if (j && j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0', '127.0.0.1');
  } catch {}
  return null;
}

(async () => {
  const ws = await getWS();
  if (!ws) {
    console.log(`SKIP: No CDP endpoint (discovery failed at ${DISCOVERY})`);
    process.exit(0);  // Skip gracefully instead of failing
  }
  console.log(`CDP: ${ws}`);
  const env = { ...process.env, BROWSERLESS_WS: ws, BASE_URL: BASE };
  const target = 'scripts/ux_check_cdp.mjs';
  if (!fs.existsSync(target)) {
    console.log('[ux_check] Minimal inline check (ux_check_cdp.mjs not found)');
    try {
      const res = await fetch(BASE, { redirect: 'manual' });
      if (!res || res.status >= 400) process.exit(1);
      process.exit(0);
    } catch {
      process.exit(1);
    }
  }
  const cp = spawn(process.execPath, [target], { stdio: 'inherit', env });
  cp.on('exit', (code) => process.exit(code ?? 0));
})();
