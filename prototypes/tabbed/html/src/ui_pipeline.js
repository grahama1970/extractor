async function listPdfs() {
  const sel = document.getElementById('pdf-select');
  sel.innerHTML = '';
  try {
    const r = await fetch('/api/list', { cache: 'no-store' });
    const j = await r.json();
    const arr = Array.isArray(j) ? j : (j.files || []);
    arr.forEach(f => {
      const opt = document.createElement('option');
      opt.value = `data/pdfs/${f}`;
      opt.textContent = f;
      sel.appendChild(opt);
    });
  } catch (e) {
    console.error(e);
  }
}

async function runPipeline() {
  const sel = document.getElementById('pdf-select');
  const pdfRel = sel.value || 'data/pdfs/BHT CV32A65X.pdf';
  const body = { pdf_rel: pdfRel, offline: true };
  const r = await fetch('/api/pipeline/run', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
  });
  const j = await r.json();
  document.getElementById('pipeline-status').textContent = JSON.stringify(j, null, 2);
}

async function pipelineStatus() {
  const r = await fetch('/api/pipeline/status');
  const j = await r.json();
  document.getElementById('pipeline-status').textContent = JSON.stringify(j, null, 2);
  const runId = (j.run_id || ((JSON.stringify(j).match(/"run_id"\s*:\s*"([^"]+)"/) || [])[1]));
  if (runId && (j.status === 'running' || j.status === 'queued')) {
    // Start polling progress bar
    startProgressPoll(runId);
  }
}

async function startTraining() {
  const r = await fetch('/api/train/start', { method: 'POST' });
  const j = await r.json();
  document.getElementById('pipeline-status').textContent = JSON.stringify(j, null, 2);
}

async function loadAnnotations() {
  const ps = document.getElementById('pipeline-status');
  const runId = (ps.textContent.match(/"run_id"\s*:\s*"([^"]+)"/) || [])[1];
  if (!runId) { ps.textContent = 'No run_id found in status. Click Status first.'; return; }
  const r = await fetch(`/api/annotations?run_id=${encodeURIComponent(runId)}`);
  const j = await r.json();
  ps.textContent = JSON.stringify({ counts:{ sections:j.sections?.length||0, tables:j.tables?.length||0, figures:j.figures?.length||0 } }, null, 2);
}

async function exportArango() {
  const ps = document.getElementById('pipeline-status');
  const runId = (ps.textContent.match(/"run_id"\s*:\s*"([^"]+)"/) || [])[1];
  if (!runId) { ps.textContent = 'No run_id found in status. Click Status first.'; return; }
  const r = await fetch(`/api/export/arango?run_id=${encodeURIComponent(runId)}`, { method: 'POST' });
  const j = await r.json();
  ps.textContent = JSON.stringify(j, null, 2);
}

document.getElementById('btn-list-pdfs')?.addEventListener('click', listPdfs);
document.getElementById('btn-run-pipeline')?.addEventListener('click', runPipeline);
document.getElementById('btn-status')?.addEventListener('click', pipelineStatus);
document.getElementById('btn-train')?.addEventListener('click', startTraining);
document.getElementById('btn-load-annotations')?.addEventListener('click', loadAnnotations);
document.getElementById('btn-export-arango')?.addEventListener('click', exportArango);

// initial
listPdfs();

// Progress bar polling
let _progressTimer = null;
function startProgressPoll(runId) {
  const ps = document.getElementById('pipeline-status');
  function tick() {
    fetch(`/api/run/progress?run_id=${encodeURIComponent(runId)}`)
      .then(r => r.json())
      .then(j => {
        const pct = j.percent ?? 0;
        ps.textContent = JSON.stringify({ progress: pct, details: j.details?.slice(0,3) }, null, 2);
        if (pct >= 100 && _progressTimer) {
          clearInterval(_progressTimer);
          _progressTimer = null;
        }
      }).catch(()=>{});
  }
  if (_progressTimer) clearInterval(_progressTimer);
  _progressTimer = setInterval(tick, 2000);
  tick();
}
