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

  // 1. Test job creation
  const run = await fetch(api + '/api/pipeline/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rel: pick.rel || pick.name, mode: 'deterministic' })
  });
  assert.equal(run.ok, true, 'pipeline run not ok');
  const jr = await run.json();
  assert.equal(jr.ok, true, 'pipeline run ok=false');
  assert.ok(jr.job_id, 'missing job_id');
  const id = jr.job_id;

  // 2. Test status endpoint - just verify it returns the job with a valid status
  // Don't wait for completion - large PDFs can take hours
  await new Promise(r => setTimeout(r, 1000)); // Brief pause for job to register
  const st = await fetch(api + '/api/pipeline/status?job_id=' + encodeURIComponent(id));
  assert.equal(st.ok, true, 'pipeline status not ok');
  const js = await st.json();
  assert.equal(js.ok, true, 'pipeline status ok=false');
  assert.ok(js.job, 'missing job in status response');
  const status = js.job.status;
  // Valid statuses are: queued, running, done, error
  assert.ok(['queued', 'running', 'done', 'error'].includes(status), `unexpected status: ${status}`);

  console.log('Smoke(api_pipeline_job): OK — job', id, 'status:', status);
  process.exit(0);
})().catch((e) => { console.error('Smoke(api_pipeline_job) failed:', e.message || e); process.exit(1); });
