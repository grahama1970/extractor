import assert from 'node:assert/strict';
import fs from 'node:fs';

async function getApiBase() {
  const candidates = [process.env.API_BASE, 'http://127.0.0.1:8001', 'http://127.0.0.1:8000'].filter(Boolean);
  for (const u of candidates) {
    try {
      const r = await fetch(u.replace(/\/$/, '') + '/api/list', { signal: AbortSignal.timeout(3000) });
      if (r.ok) return u.replace(/\/$/, '');
    } catch {}
  }
  console.log('SKIP: No API server reachable (set API_BASE or start server on 8001/8000).');
  process.exit(3);
}

(async () => {
  const api = await getApiBase();
  const listRes = await fetch(api + '/api/list');
  assert.equal(listRes.ok, true, 'list endpoint not ok');
  const list = await listRes.json();
  assert.equal(list.ok, true, 'list payload ok=false');
  assert.ok(Array.isArray(list.items) && list.items.length > 0, 'no pdf items');
  const pick = list.items.find((x) => x.name.toLowerCase() === 'bht cv32a65x.pdf') || list.items[0];
  const payload = { rel: pick.rel || pick.name, boxes_by_page: { '1': [ { x: 0.1, y: 0.1, w: 0.2, h: 0.15, type: 'Table' } ] } };
  const r = await fetch(api + '/api/coco/export', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
  assert.equal(r.ok, true, 'coco export not ok');
  const j = await r.json();
  assert.equal(j.ok, true, 'coco export ok=false');
  assert.ok(typeof j.dir === 'string' && j.dir.length > 0, 'missing dir');
  assert.ok(typeof j.json === 'string' && j.json.length > 0, 'missing json path');
  assert.ok(fs.existsSync(j.dir), 'artifacts dir missing');
  assert.ok(fs.existsSync(j.json), 'annotations.json missing');
  // Optional: browse endpoint returns html
  const b = await fetch(api + '/api/artifacts/browse?dir=' + encodeURIComponent(j.dir));
  assert.equal(b.ok, true, 'browse not ok');
  const html = await b.text();
  assert.ok(html.includes('Artifacts'), 'browse not html-like');
  console.log('Smoke(api_coco_export): OK —', j.dir);
  process.exit(0);
})().catch((e) => { console.error('Smoke(api_coco_export) failed:', e.message || e); process.exit(1); });
