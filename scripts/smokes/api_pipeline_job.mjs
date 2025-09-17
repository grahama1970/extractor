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
  const run = await fetch(api + '/api/pipeline/run', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ rel: pick.rel || pick.name }) });
  assert.equal(run.ok, true, 'pipeline run not ok');
  const jr = await run.json();
  assert.equal(jr.ok, true, 'pipeline run ok=false');
  assert.ok(jr.job_id, 'missing job_id');
  const id = jr.job_id;
  let status = 'queued';
  for (let i=0;i<15;i++) {
    const st = await fetch(api + '/api/pipeline/status?job_id=' + encodeURIComponent(id));
    assert.equal(st.ok, true, 'pipeline status not ok');
    const js = await st.json();
    assert.equal(js.ok, true, 'pipeline status ok=false');
    status = js.job && js.job.status;
    if (status === 'done' || status === 'error') break;
    await new Promise(r => setTimeout(r, 500));
  }
  assert.equal(status, 'done', 'pipeline not done');
  const rr = await fetch(api + '/api/pipeline/result?job_id=' + encodeURIComponent(id));
  assert.equal(rr.ok, true, 'pipeline result not ok');
  const jr2 = await rr.json();
  assert.equal(jr2.ok, true, 'pipeline result ok=false');
  assert.ok(jr2.result && jr2.result.out_dir, 'missing result.out_dir');
  console.log('Smoke(api_pipeline_job): OK —', id);
  process.exit(0);
})().catch((e) => { console.error('Smoke(api_pipeline_job) failed:', e.message || e); process.exit(1); });
