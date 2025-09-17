import fs from 'node:fs';
import path from 'node:path';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080';
const OUT_DIR = path.resolve('scripts', 'artifacts');
fs.mkdirSync(OUT_DIR, { recursive: true });
const ts = () => new Date().toISOString().replace(/[:.]/g, '-');

(async () => {
  const origin = new URL(BASE).origin;
  const health = await (await fetch(origin + '/api/health/llm')).json().catch(()=>null);
  if (!health || health.ok !== true || !health.model) {
    console.error('LLM health not OK or model missing');
    process.exit(1);
  }
  const expectedModel = health.model;

  const prompt = 'Return only {"ok":true} as JSON.';
  const resp = await fetch(origin + '/api/ux/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  }).catch(()=>null);
  if (!resp || !resp.ok) {
    console.error('POST /api/ux/generate failed');
    process.exit(1);
  }
  const data = await resp.json().catch(()=>null);
  let obj = null;
  if (data && data.ok && data.data) {
    obj = data.data.json || data.data.output || data.data.text || data.data;
    if (typeof obj === 'string') { try { obj = JSON.parse(obj); } catch {} }
  }
  const ok = obj && obj.ok === true;
  const hasModel = obj && typeof obj.model === 'string';
  const matches = hasModel && obj.model === expectedModel;

  const stamp = ts();
  const logPath = path.join(OUT_DIR, `api_generate_model_${stamp}.log`);
  fs.writeFileSync(logPath, [
    `BASE_URL=${BASE}`,
    `expectedModel=${expectedModel}`,
    `ok=${ok}`,
    `hasModel=${!!hasModel}`,
    `returnedModel=${hasModel ? obj.model : ''}`,
  ].join('\n'));

  if (!(ok && hasModel && matches)) {
    console.error('API generate model check failed');
    process.exit(1);
  }
  console.log('Smoke(api_generate_model): OK');
  process.exit(0);
})().catch((e) => { console.error('Smoke(api_generate_model) crashed:', e.message || e); process.exit(2); });

