import puppeteer from 'puppeteer';

const BASE = process.env.BASE_URL || 'http://localhost:8080/main';
const wait = (ms) => new Promise(r => setTimeout(r, ms));

async function drag(page, selector, dx, dy) {
  const r = await page.$eval(selector, el => { const b=el.getBoundingClientRect(); return {x:b.left + Math.min(150, Math.max(12, b.width-20)), y:b.top + 12}; });
  await page.mouse.move(r.x, r.y, { steps: 2 });
  await page.mouse.down();
  await page.mouse.move(r.x + dx, r.y + dy, { steps: 8 });
  await page.mouse.up();
}

async function main() {
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  page.setDefaultTimeout(20000);
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });

  // HUD and overlay present
  await page.waitForSelector('[data-testid="hud"]');
  await wait(400);
  // There should be exactly one + icon in HUD (palette)
  const plusCount = await page.$$eval('svg.lucide.lucide-plus', els => els.length).catch(()=>0);
  if (plusCount !== 1) throw new Error(`Expected exactly one + icon in HUD, found ${plusCount}`);


  // 1) Palette sets type to Figure
  await page.click('[data-testid="hud-plus"]', { delay: 20 });
  await wait(250);
  if (!(await page.$('[data-testid=\"label-palette\"]'))) {
    await page.click('[data-testid="hud-plus"]', { delay: 20 });
  }
  await page.waitForSelector('[data-testid="label-palette"]', { timeout: 4000 });
  await page.click('[data-testid="label-item-figure"]');
  await wait(150);
  const txt = await page.$eval('div.relative.inline-block > div.absolute.inset-0 div.absolute.-top-6', el => el.textContent.toLowerCase());
  if (!txt.includes('figure')) throw new Error('Palette did not set type to Figure');

  // 2) Persist HUD position across reload (simulate move via localStorage write)
  const before = await page.$eval('[data-testid="hud"]', el => { const b=el.getBoundingClientRect(); return {x:b.left,y:b.top}; });
  await page.evaluate((pos)=>{ localStorage.setItem('anno_hud_pos', JSON.stringify({ x: pos.x + 120, y: pos.y + 80 })); localStorage.setItem('anno_hud_mode','free'); }, before);
  await page.reload({ waitUntil: 'domcontentloaded' });
  const after = await page.$eval('[data-testid="hud"]', el => { const b=el.getBoundingClientRect(); return {x:b.left,y:b.top}; });
  if (Math.hypot(after.x - before.x, after.y - before.y) < 60) throw new Error('HUD position did not persist');

  // 3) Draw on page 1 and page 2 (arm Draw mode), then verify persistence after reload
  const overlaySel = 'div.relative.inline-block > div.absolute.inset-0';
  await page.waitForSelector(overlaySel, { timeout: 5000 });
  const rect = await page.$eval(overlaySel, el => { const r=el.getBoundingClientRect(); return {x:r.left,y:r.top,w:r.width,h:r.height};});
  await page.click('[data-testid="hud-new"]');
  await page.mouse.move(rect.x + rect.w*0.25, rect.y + rect.h*0.25);
  await page.mouse.down();
  await page.mouse.move(rect.x + rect.w*0.55, rect.y + rect.h*0.38, { steps: 8 });
  await page.mouse.up();
  const count1 = await page.$$eval(`${overlaySel} [data-testid="box"]`, els => els.length).catch(()=>0);
  if (count1 < 1) throw new Error('No box drawn on page 1');

  await page.keyboard.press(']');
  await wait(600);
  const rect2 = await page.$eval(overlaySel, el => { const r=el.getBoundingClientRect(); return {x:r.left,y:r.top,w:r.width,h:r.height};});
  await page.click('[data-testid="hud-new"]');
  await page.mouse.move(rect2.x + rect2.w*0.30, rect2.y + rect2.h*0.30);
  await page.mouse.down();
  await page.mouse.move(rect2.x + rect2.w*0.62, rect2.y + rect2.h*0.62, { steps: 8 });
  await page.mouse.up();
  const count2 = await page.$$eval(`${overlaySel} [data-testid="box"]`, els => els.length).catch(()=>0);
  console.log('page2 box count:', count2);
  if (count2 < 1) throw new Error('No box drawn on page 2');

  await page.reload({ waitUntil: 'domcontentloaded' });
  await wait(250);
  for (let i=0;i<3;i++) await page.keyboard.press('[');
  const persisted1 = await page.$$eval(`${overlaySel} [data-testid="box"]`, els => els.length).catch(()=>0);
  if (persisted1 < 1) throw new Error('Page 1 box did not persist after reload');

  console.log('MB-003 smoke: OK');
  await browser.close();
}

main().catch((e)=>{ console.error('MB-003 smoke failed:', e.message); process.exit(1); });
