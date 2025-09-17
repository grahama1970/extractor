import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080/main';
const MODEL = process.env.MODEL || process.env.LITELLM_DEFAULT_MODEL || process.env.DEFAULT_LITELLM_MODEL || '';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });

const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

(async () => {
  const origin = new URL(BASE).origin;
  const url = origin + '/api/health/llm' + (MODEL ? ('?model=' + encodeURIComponent(MODEL)) : '');
  let status = 0;
  let bodyText = '';
  let body = null;
  try {
    const resp = await fetch(url, { headers: { 'accept': 'application/json' } });
    status = resp.status;
    bodyText = await resp.text();
    try { body = JSON.parse(bodyText); } catch {}
  } catch (e) {
    const log = [
      `url=${url}`,
      `error=${e?.message || e}`,
    ].join('\n');
    const logPath = path.join(OUT_DIR, `llm_health_${ts()}.log`);
    fs.writeFileSync(logPath, log, 'utf-8');
    console.error('Smoke(llm_health) failed: fetch error');
    process.exit(2);
  }

  const ok = !!(body && body.ok === true);
  const log = [
    `url=${url}`,
    `status=${status}`,
    `ok=${ok}`,
    `model=${body?.model || MODEL || ''}`,
    '--- body ---',
    bodyText,
  ].join('\n');
  const logPath = path.join(OUT_DIR, `llm_health_${ts()}.log`);
  fs.writeFileSync(logPath, log, 'utf-8');

  if (!ok) {
    console.error('Smoke(llm_health) failed: endpoint did not return ok=true');
    process.exit(1);
  }
  console.log('Smoke(llm_health): OK');
  process.exit(0);
})();
