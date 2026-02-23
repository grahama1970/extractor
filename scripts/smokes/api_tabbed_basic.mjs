// API-only smoke for tabbed prototype: validates list and pdf endpoints.
import assert from 'node:assert/strict';

async function getApiBase() {
  const candidates = [process.env.API_BASE, 'http://127.0.0.1:8001', 'http://127.0.0.1:8000'].filter(Boolean);
  for (const u of candidates) {
    try {
      const r = await fetch(u.replace(/\/$/, '') + '/api/list', { signal: AbortSignal.timeout(3000) });
      if (r.ok) return u.replace(/\/$/, '');
    } catch {}
  }
  // Exit code 3 = skip (no API server available), consistent with CDP smoke behavior
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
  const names = list.items.map((x) => x.name);
  const pick = list.items.find((x) => x.name.toLowerCase() === 'bht cv32a65x.pdf') || list.items[0];

  const pdfUrl = api + '/api/pdf?rel=' + encodeURIComponent(pick.rel || pick.name);
  const pdfRes = await fetch(pdfUrl);
  assert.equal(pdfRes.ok, true, 'pdf endpoint not ok');
  const ctype = pdfRes.headers.get('content-type') || '';
  assert.ok(ctype.includes('application/pdf'), 'pdf content-type mismatch: ' + ctype);
  const buf = Buffer.from(await pdfRes.arrayBuffer());
  assert.ok(buf.length > 1000, 'pdf too small: ' + buf.length);

  console.log('Smoke(api_tabbed_basic): OK —', pick.name, buf.length, 'bytes');
  process.exit(0);
})().catch((e) => { console.error('Smoke(api_tabbed_basic) failed:', e.message || e); process.exit(1); });

