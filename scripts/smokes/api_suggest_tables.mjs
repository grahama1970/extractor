import assert from 'node:assert/strict';

async function getApiBase() {
  const candidates = [process.env.API_BASE, 'http://127.0.0.1:8001', 'http://127.0.0.1:8000'].filter(Boolean);
  for (const u of candidates) {
    try {
      const r = await fetch(u.replace(/\/$/, '') + '/api/list');
      if (r.ok) return u.replace(/\/$/, '');
    } catch {}
  }
  throw new Error('API base not reachable on 8001/8000');
}

(async () => {
  const api = await getApiBase();
  const listRes = await fetch(api + '/api/list');
  const list = await listRes.json();
  const pick = (list.items || [])[0];
  if (!pick) throw new Error('no pdf items');
  const r = await fetch(api + '/api/suggest/tables?rel=' + encodeURIComponent(pick.rel || pick.name) + '&page=1');
  const j = await r.json().catch(()=>({}));
  if (j && j.error === 'camelot_missing') {
    console.log('Smoke(api_suggest_tables): SKIP — camelot missing (endpoint reachable)');
    process.exit(0);
  }
  assert.equal(r.ok, true, 'suggest not ok');
  assert.equal(j.ok, true, 'suggest ok=false');
  if (!Array.isArray(j.suggestions)) throw new Error('suggestions not array');
  console.log('Smoke(api_suggest_tables): OK —', j.suggestions.length, 'suggestions');
  process.exit(0);
})().catch((e) => { console.error('Smoke(api_suggest_tables) failed:', e.message || e); process.exit(1); });
