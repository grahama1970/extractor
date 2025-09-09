/*
 JSON interactions runner for Puppeteer.
 Usage:
   node tests/interactions/run.js --pattern render,boxes --headless=true --baseUrl=http://localhost:3002
 Env:
   BASE_URL overrides per-file baseUrl.
*/

const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer');

function sleep(ms){ return new Promise(r=>setTimeout(r, ms)); }


function parseArgs(argv) {
  const args = {};
  for (const a of argv.slice(2)) {
    const m = a.match(/^--([^=]+)=(.*)$/);
    if (m) args[m[1]] = m[2];
    else if (a.startsWith('--')) args[a.slice(2)] = true;
  }
  return args;
}

function readJsonFiles(dir) {
  return fs
    .readdirSync(dir)
    .filter((f) => f.endsWith('.json'))
    .map((f) => ({ name: path.basename(f, '.json'), file: path.join(dir, f) }));
}

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

async function clickByText(page, tag, text) {
  const el = await page.evaluateHandle(
    ({ tag, text }) => {
      const hay = Array.from(document.querySelectorAll(tag));
      return hay.find((e) => (e.innerText || '').trim().includes(text));
    },
    { tag, text }
  );
  if (!el) throw new Error(`No <${tag}> containing text: ${text}`);
  const box = await el.boundingBox();
  if (!box) throw new Error(`Element <${tag}> not visible: ${text}`);
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2);
}

async function findByText(page, text) {
  return await page.evaluateHandle(
    (text) => {
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let n;
      while ((n = walker.nextNode())) {
        if ((n.nodeValue || '').includes(text)) return n.parentElement;
      }
      return null;
    },
    text
  );
}

async function runStep(page, step) {
  switch (step.action) {
    case 'goto': {
      const url = step.url.startsWith('http') ? step.url : new URL(step.url, page.__baseUrl).toString();
      await page.goto(url, { waitUntil: 'domcontentloaded' });
      break;
    }
    case 'reload': {
      await page.reload({ waitUntil: 'domcontentloaded' });
      break;
    }
    case 'screenshot': {
      const out = step.path;
      ensureDir(path.dirname(out));
      await page.screenshot({ path: out, fullPage: !!step.fullPage });
      break;
    }
    case 'fill': {
      const sel = step.selector;
      await page.waitForSelector('*');
      await sleep(50);
      await page.focus(sel);
      await page.click(sel, { clickCount: 3 });
      await page.type(sel, step.value, { delay: 1 });
      break;
    }
    case 'select': {
      await page.select(step.selector, step.value);
      break;
    }
    case 'click': {
      const sel = step.selector;
      if (/^button:has-text\(['"](.+?)['"]\)$/.test(sel)) {
        const text = sel.match(/^button:has-text\(['"](.+?)['"]\)$/)[1];
        await clickByText(page, 'button', text);
      } else if (/^text=(.+)$/.test(sel)) {
        const text = sel.match(/^text=(.+)$/)[1];
        const handle = await findByText(page, text);
        if (!handle) throw new Error(`No element matching text=${text}`);
        const box = await handle.boundingBox();
        if (!box) throw new Error(`Element for text=${text} not visible`);
        await page.mouse.click(box.x + 4, box.y + 4);
      } else {
        await page.click(sel);
      }
      break;
    }
    case 'wait': {
      if (step.for === 'selector') {
        await page.waitForSelector(step.selector, { timeout: step.timeout || 15000 });
      } else if (step.for === 'networkidle') {
        await page.waitForNetworkIdle({ idleTime: 500, timeout: 20000 });
      } else if (step.for === 'timeout') {
        await sleep(step.ms || 500);
      }
      break;
    }
    case 'mouse': {
      if (step.type === 'move') await page.mouse.move(step.x, step.y);
      else if (step.type === 'down') await page.mouse.down({ button: step.button || 'left' });
      else if (step.type === 'up') await page.mouse.up({ button: step.button || 'left' });
      break;
    }
    case 'key': {
      if (step.type === 'press') {
        const parts = step.key.split('+');
        const mods = parts.slice(0, -1);
        const key = parts[parts.length - 1];
        for (const m of mods) await page.keyboard.down(m.replace('Control', 'Control'));
        await page.keyboard.press(key);
        for (const m of mods.reverse()) await page.keyboard.up(m.replace('Control', 'Control'));
      } else if (step.type === 'type') {
        await page.keyboard.type(step.text);
      }
      break;
    }
    default:
      throw new Error(`Unknown action: ${step.action}`);
  }
}

async function runFlow(browser, flowFile, baseUrl) {
  const flow = JSON.parse(fs.readFileSync(flowFile, 'utf8'));
  const page = await browser.newPage();
  page.setDefaultTimeout(15000);
  page.__baseUrl = process.env.BASE_URL || baseUrl || flow.baseUrl || 'http://localhost:3002';
  console.log(`\n==> Flow: ${flow.name} @ ${page.__baseUrl}`);
  if (flow.prereq) console.log(`Prereq: ${flow.prereq}`);
  for (const [i, step] of (flow.steps || []).entries()) {
    try {
      console.log(`  [${String(i + 1).padStart(2, '0')}] ${step.action}`);
      await runStep(page, step);
    } catch (e) {
      console.error(`  Step ${i + 1} failed:`, e.message);
      // Capture an error screenshot to aid debugging
      try {
        ensureDir('tools/gold_annotator_web/docs/screenshots/_errors');
        await page.screenshot({ path: `tools/gold_annotator_web/docs/screenshots/_errors/${path.basename(flowFile)}_${i + 1}.png`, fullPage: true });
      } catch {}
      throw e;
    }
  }
  await page.close();
}

async function main() {
  const args = parseArgs(process.argv);
  const headless = args.headless !== 'false';
  const pattern = (args.pattern || '').split(',').map((s) => s.trim()).filter(Boolean);
  const baseUrl = args.baseUrl;
  const dir = path.join('tools', 'gold_annotator_web', 'tests', 'interactions');
  const files = readJsonFiles(dir);
  const chosen = pattern.length
    ? files.filter((f) => pattern.some((p) => f.name.includes(p)))
    : files;

  if (!chosen.length) {
    console.error('No interaction files match pattern:', pattern.join(','));
    process.exit(1);
  }

  const browser = await puppeteer.launch({ headless, args: ['--no-sandbox', '--disable-setuid-sandbox'] });
  try {
    for (const f of chosen) {
      await runFlow(browser, f.file, baseUrl);
    }
  } finally {
    await browser.close();
  }
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});

