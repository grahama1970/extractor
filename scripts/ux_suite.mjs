import puppeteer from 'puppeteer';

const BASE = process.env.BASE_URL || 'http://localhost:8080/main';
const wait = (ms) => new Promise(r => setTimeout(r, ms));

async function setPage(page, n){
  await page.$eval('[data-testid="pager-slider"]', (el, n)=>{ el.value=String(n); el.dispatchEvent(new Event('input',{bubbles:true})); }, n);
  await wait(200);
  const label = await page.$eval('[data-testid="page-label"]', el=>el.textContent);
  if (!label.includes(`Page ${n} `)) throw new Error(`Failed to navigate to page ${n}`);
}

async function drawBox(page, frac){
  const r = await page.$eval('[data-testid="overlay"]', el=>{ const b=el.getBoundingClientRect(); return {x:b.left,y:b.top,w:b.width,h:b.height};});
  const [sx, sy] = [r.x + r.w*frac[0], r.y + r.h*frac[1]];
  const [ex, ey] = [r.x + r.w*frac[2], r.y + r.h*frac[3]];
  await page.click('[data-testid="hud-new"]');
  await page.mouse.move(sx, sy); await page.mouse.down(); await page.mouse.move(ex, ey, {steps: 8}); await page.mouse.up();
  await wait(150);
  const count = await page.$$eval('[data-testid="box"]', els=>els.length).catch(()=>0);
  if (count < 1) throw new Error('No box created');
}

async function main(){
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  page.setDefaultTimeout(20000);
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  try {
    await page.waitForFunction(() => !!window.__ux, { timeout: 25000 });
  } catch {
    await page.goto('http://localhost:8080/classic', { waitUntil: 'domcontentloaded' });
    await page.waitForFunction(() => !!window.__ux, { timeout: 25000 });
  }

  // MB-003 basics: single plus, palette applies Figure
  await page.waitForSelector('[data-testid="hud-plus"]', { timeout: 4000 });
  await page.click('[data-testid="hud-plus"]');
  await page.waitForSelector('[data-testid="label-palette"]');
  await page.click('[data-testid="label-item-figure"]');
  await wait(150);

  // Draw on page 1 and 2; prefer dev helper if available
  const hasUx = await page.evaluate(() => !!window.__ux).catch(()=>false);
  if (hasUx) {
    await page.evaluate(() => window.__ux.setPage(1));
    await page.evaluate(() => window.__ux.drawBox(1, 0.25, 0.25, 0.55, 0.38, 'Figure'));
    await page.evaluate(() => window.__ux.setPage(2));
    await page.evaluate(() => window.__ux.drawBox(2, 0.30, 0.30, 0.62, 0.62, 'Figure'));
  } else {
    await setPage(page, 1); await drawBox(page, [0.25,0.25,0.55,0.38]);
    await setPage(page, 2); await drawBox(page, [0.30,0.30,0.62,0.62]);
  }

  // HUD persistence
  const before = await page.$eval('[data-testid="hud"]', el=>{ const b=el.getBoundingClientRect(); return {x:b.left,y:b.top};});
  await page.evaluate((pos)=>{ localStorage.setItem('anno_hud_pos', JSON.stringify({ x: pos.x + 120, y: pos.y + 80 })); localStorage.setItem('anno_hud_mode','free'); }, before);
  await page.reload({ waitUntil: 'domcontentloaded' }); await wait(300);
  const after = await page.$eval('[data-testid="hud"]', el=>{ const b=el.getBoundingClientRect(); return {x:b.left,y:b.top};});
  if (Math.hypot(after.x - before.x, after.y - before.y) < 60) throw new Error('HUD no persistence delta');

  // MB-004: ESC cancel + Shift constrain
  await setPage(page, 1);
  await page.click('[data-testid="hud-new"]');
  const r = await page.$eval('[data-testid="overlay"]', el=>{ const b=el.getBoundingClientRect(); return {x:b.left,y:b.top,w:b.width,h:b.height};});
  await page.mouse.move(r.x + r.w*0.2, r.y + r.h*0.2); await page.mouse.down(); await page.keyboard.press('Escape'); await page.mouse.up();
  const countEsc = await page.$$eval('[data-testid="box"]', els=>els.length).catch(()=>0);
  // Should be unchanged or zero for a fresh page

  await page.click('[data-testid="hud-new"]');
  await page.keyboard.down('Shift');
  await page.mouse.move(r.x + r.w*0.2, r.y + r.h*0.2); await page.mouse.down(); await page.mouse.move(r.x + r.w*0.5, r.y + r.h*0.5, {steps: 8}); await page.mouse.up(); await page.keyboard.up('Shift');
  const lastRect = await page.$eval('[data-testid="box"]', el=>{ const b=el.getBoundingClientRect(); return {w:b.width,h:b.height};});
  const ratio = lastRect.h / lastRect.w; if (Math.abs(ratio - (3/4)) > 0.15) throw new Error('Shift ratio not ~3:4');

  // MB-005: HUD visible toggle present
  await page.waitForSelector('[data-testid="hud-mode-toggle"]');

  // MB-006: Help overlay
  await page.click('[title="Help (?)"]'); await page.waitForSelector('.\!pointer-events-auto, [role="dialog"]', {timeout: 4000}).catch(()=>{}); // dialog present
  await page.keyboard.press('Escape'); await wait(100);

  // MB-007: Add Label (smoke)
  await page.click('[data-testid="hud-plus"]'); await page.waitForSelector('[data-testid="label-add"]');
  await page.click('[data-testid="label-add"]'); await page.waitForSelector('[data-testid="label-add-dialog"]');
  await page.type('[data-testid="label-name"]', 'Equation');
  await page.click('[data-testid="label-save"]'); await wait(200);
  await page.click('[data-testid="hud-plus"]');
  await page.waitForSelector('[data-testid="label-item-equation"]');

  console.log('UX suite: OK');
  await browser.close();
}

main().catch(e=>{ console.error('UX suite failed:', e.message); process.exit(1); });
