import puppeteer from 'puppeteer';
const BASE = process.env.BASE_URL || 'http://localhost:8080/main';
const wait = (ms) => new Promise(r => setTimeout(r, ms));

async function main(){
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  page.setDefaultTimeout(20000);
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await wait(300);
  // Open palette
  await page.click('[data-testid="hud-plus"]');
  // Expect Add Label button (not yet implemented will cause failure; this is a spec-driven test)
  await page.waitForSelector('[data-testid="label-add"]', { timeout: 4000 });
  await page.click('[data-testid="label-add"]');
  await page.waitForSelector('[data-testid="label-add-dialog"]');
  await page.type('[data-testid="label-name"]', 'Equation');
  // Icon/color selectors will be specific once implemented; placeholder selectors below
  if (await page.$('[data-testid="icon-select"]')) {
    await page.click('[data-testid="icon-select"]');
    await page.click('[data-testid="icon-option-Sigma"]');
  }
  if (await page.$('[data-testid="color-select"]')) {
    await page.click('[data-testid="color-select"]');
    await page.click('[data-testid="color-option-annotation-equation"]');
  }
  await page.click('[data-testid="label-save"]');
  await wait(200);
  // Palette shows new label
  await page.waitForSelector('[data-testid="label-item-equation"]');
  // Reload and assert persistence
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.click('[data-testid="hud-plus"]');
  await page.waitForSelector('[data-testid="label-item-equation"]');
  console.log('MB-007 Add Label: OK');
  await browser.close();
}

main().catch(e=>{ console.error('MB-007 Add Label failed:', e.message); process.exit(1); });
