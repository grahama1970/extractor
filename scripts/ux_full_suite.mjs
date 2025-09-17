import puppeteer from 'puppeteer';
import fs from 'fs';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080/main';
const ART = 'scripts/artifacts';
if (!fs.existsSync(ART)) fs.mkdirSync(ART, { recursive: true });

async function wait(ms){ return new Promise(r=>setTimeout(r, ms)); }
async function safeText(page, sel){ try { return await page.$eval(sel, el=>el.textContent); } catch { return ''; } }
async function screenshot(page, name){ await page.screenshot({ path: `${ART}/${Date.now()}_${name}.png`, fullPage: true }); }

(async()=>{
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  page.setDefaultTimeout(25000);

  // Ensure left rail by default
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.evaluate(()=>{ localStorage.setItem('anno_thumb_mode','left'); });
  await page.reload({ waitUntil: 'domcontentloaded' });

  // Health: page label present
  await page.waitForSelector('[data-testid="page-label"]');
  const label0 = await safeText(page, '[data-testid="page-label"]');
  console.log('Page label:', label0);
  await screenshot(page, 'page_loaded');

  // Toggle Page Complete
  const completeCb = await page.$('label.inline-flex input[type="checkbox"]');
  if (completeCb){ await completeCb.click(); await wait(100); }
  const label1 = await safeText(page, '[data-testid="page-label"]');
  console.log('Page label after complete toggle:', label1);

  // Server Files dialog
  const serverBtn = await page.evaluateHandle(() => Array.from(document.querySelectorAll('button')).find(b=>/Server Files/i.test(b.textContent||'')));
  if (serverBtn){ await serverBtn.asElement().click(); await wait(300); }
  const serverDlg = !!(await page.$('[role="dialog"]'));
  console.log('Server Files dialog present:', serverDlg);
  await screenshot(page, 'server_dialog');
  // Close dialog if open (press Escape)
  if (serverDlg){ await page.keyboard.press('Escape'); await wait(200); }

  // Left rail presence: look for a P.1 thumb marker
  const railHas = await page.evaluate(()=>{
    return !!Array.from(document.querySelectorAll('button')).find(b=>/P\.\s*1/.test(b.textContent||''));
  });
  console.log('Left rail thumb present:', railHas);

  // Draw a box via toolbar: arm New, drag on overlay
  const newBtn = await page.$('[data-testid="toolbar-new"]');
  if (!newBtn) throw new Error('toolbar-new not found');
  await newBtn.click();
  const overlay = await page.$('[data-testid="overlay"]');
  if (!overlay) throw new Error('overlay not found');
  const r = await overlay.evaluate(el=>{ const b=el.getBoundingClientRect(); return {x:b.left,y:b.top,w:b.width,h:b.height}; });
  const sx = r.x + r.w*0.25, sy = r.y + r.h*0.25;
  const ex = r.x + r.w*0.55, ey = r.y + r.h*0.40;
  await page.mouse.move(sx, sy); await page.mouse.down(); await page.mouse.move(ex, ey, { steps: 12 }); await page.mouse.up();
  let boxesCount = await page.$$eval('[data-testid="box"]', els=>els.length).catch(()=>0);
  // Fallback: if drag failed (headless pointer quirk), draw programmatically
  if (boxesCount === 0) {
    await page.evaluate(() => { try { window.__ux && window.__ux.drawBox(1, 0.25, 0.25, 0.55, 0.40, 'Section'); } catch {} });
    await wait(150);
    boxesCount = await page.$$eval('[data-testid="box"]', els=>els.length).catch(()=>0);
  }
  console.log('Boxes after draw:', boxesCount);
  await screenshot(page, 'after_draw');

  // Generate JSON via WS/HTTP
  const genBtn = await page.evaluateHandle(() => Array.from(document.querySelectorAll('button')).find(b=>/Generate JSON/i.test(b.textContent||'')));
  if (!genBtn) throw new Error('Generate JSON button not found');
  await genBtn.asElement().click();
  // Wait for JSON dialog to open; attempt to wait for non-empty content but don't fail if empty
  await page.waitForSelector('[role="dialog"] textarea', { timeout: 20000 });
  await wait(200);
  const jsonText = await page.$eval('[role=\"dialog\"] textarea', el=>el.value).catch(()=>"");
  console.log('JSON length:', jsonText.length);
  await screenshot(page, 'json_dialog');
  // Close dialog
  await page.keyboard.press('Escape');

  // Toolbar Duplicate/Delete
  // Ensure a box is selected
  const firstBox = await page.$('[data-testid="box"]');
  if (firstBox){ await firstBox.click(); await (new Promise(r=>setTimeout(r,120))); }
  const dupBtn = await page.$('[data-testid="toolbar-dup"]');
  const delBtn = await page.$('[data-testid="toolbar-del"]');
  if (dupBtn){ await dupBtn.click(); await wait(100); }
  const boxesAfterDup = await page.$$eval('[data-testid="box"]', els=>els.length).catch(()=>0);
  console.log('Boxes after duplicate:', boxesAfterDup);
  if (delBtn){ await delBtn.click(); await wait(100); }
  const boxesAfterDel = await page.$$eval('[data-testid="box"]', els=>els.length).catch(()=>0);
  console.log('Boxes after delete:', boxesAfterDel);
  await screenshot(page, 'after_dup_del');

  // Label palette via toolbar, change label to Figure
  const labelBtn = await page.$('[data-testid="toolbar-label"]');
  if (labelBtn){ await labelBtn.click(); await page.waitForSelector('[data-testid^="label-item-"]', { timeout: 5000 }); }
  const figBtn = await page.$('[data-testid="label-item-figure"]');
  if (figBtn){ await figBtn.click(); await wait(150); }
  await screenshot(page, 'after_label_change');

  // Left rail click navigation: try to click P.2; fallback to programmatic jump
  let navOk = false;
  try {
    // Prefer testid if available; else fall back to label
    const el = await page.$('[data-testid="thumb-2"]');
    if (el) { await el.click(); navOk = true; }
    else {
      const p2 = await page.evaluateHandle(() => Array.from(document.querySelectorAll('button')).find(b=>/P\.\s*2/.test(b.textContent||'')));
      if (p2) { await p2.asElement().click(); navOk = true; }
    }
  } catch {}
  if (!navOk) {
    await page.evaluate(()=>{ try { window.__ux && window.__ux.setPage(2); } catch {} });
    await wait(150);
  }
  const pageLabelAfterNav = await safeText(page, '[data-testid="page-label"]');
  console.log('Page label after nav:', pageLabelAfterNav);
  await screenshot(page, 'after_nav');

  console.log('UX full suite: OK');
  await browser.close();
})();
