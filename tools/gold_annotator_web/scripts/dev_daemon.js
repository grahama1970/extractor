#!/usr/bin/env node
// Lightweight dev daemon: keeps `next dev` running in the background with polling watchers.
// Usage: node scripts/dev_daemon.js start|stop|status

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const PID_FILE = path.join(__dirname, '..', '.next-dev.pid');
const LOG_FILE = path.join(__dirname, '..', '.next-dev.log');
const PORT = process.env.PORT || '3002';
const PORT_FILE = path.join(__dirname, '..', '.next-dev.port');

function isAlive(pid) {
  try { process.kill(pid, 0); return true; } catch { return false; }
}

function readPid() {
  try { return parseInt(fs.readFileSync(PID_FILE, 'utf8').trim(), 10); } catch { return null; }
}

function writePid(pid) {
  fs.writeFileSync(PID_FILE, String(pid));
}

function removePid() {
  try { fs.unlinkSync(PID_FILE); } catch {}
}

function pickPort(preferred) {
  const candidates = [preferred, '3003', '3004', '3005'];
  for (const p of candidates) {
    try {
      const out = require('child_process').execSync(`ss -ltnp | grep :${p} `, { stdio: 'pipe' }).toString();
      if (!out.includes(`:${p} `)) return p;
    } catch {
      return p;
    }
  }
  return preferred;
}

function start() {
  const existing = readPid();
  if (existing && isAlive(existing)) {
    console.log(`dev daemon already running (pid ${existing})`);
    process.exit(0);
  }
  try { fs.writeFileSync(PORT_FILE, String(PORT)); } catch {}
  const script = `while true; do \\
    WATCHPACK_POLLING=true CHOKIDAR_USEPOLLING=1 PORT=${PORT} npx next dev -H 0.0.0.0 -p ${PORT} >> ${LOG_FILE} 2>&1; \\
    echo 'dev server exited; restarting in 1s' >> ${LOG_FILE}; \\
    sleep 1; \\
  done`;
  const child = spawn('bash', ['-c', script], {
    cwd: path.join(__dirname, '..'),
    detached: true,
    stdio: 'ignore',
  });
  child.unref();
  writePid(child.pid);
  console.log(`started dev daemon (pid ${child.pid}), logging to ${LOG_FILE}`);
}

function stop() {
  const pid = readPid();
  if (!pid) { console.log('no pid file; nothing to stop'); return; }
  try {
    process.kill(pid, 'SIGTERM');
    removePid();
    try { fs.unlinkSync(PORT_FILE); } catch {}
    console.log(`stopped dev daemon (pid ${pid})`);
  } catch (e) {
    console.log(`failed to stop pid ${pid}: ${e.message}`);
  }
}

function status() {
  const pid = readPid();
  if (pid && isAlive(pid)) {
    let port=null; try{port=fs.readFileSync(PORT_FILE,'utf8').trim();}catch{}
    console.log(`dev daemon running (pid ${pid}) on port ${port||'3002'}; tail -f ${LOG_FILE}`);
  } else {
    console.log('dev daemon not running');
  }
}

const cmd = process.argv[2] || 'status';
if (cmd === 'start') start();
else if (cmd === 'stop') stop();
else status();

