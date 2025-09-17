import puppeteer from 'puppeteer';
const BASE = process.env.BASE_URL || 'http://127.0.0.1:5173/main';
const wait = (ms)=>new Promise(r=>setTimeout(r,ms));

(async()=>{
  const browser = await puppeteer.launch({ headless: 'new', args: ['--no-sandbox','--disable-setuid-sandbox'] });
  const page = await browser.newPage();
  page.setDefaultTimeout(20000);
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  await page.evaluate(()=>{ localStorage.setItem('anno_thumb_mode','left'); });
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="page-label"]');
  // Toggle page complete
  const labelBefore = await page.$eval('[data-testid="page-label"]', el=>el.textContent);
  const completeCb = await page.$('label.inline-flex input[type="checkbox"]');
  if (completeCb){ await completeCb.click(); }
  await wait(150);
  const labelAfter = await page.$eval('[data-testid="page-label"]', el=>el.textContent);
  console.log('Page label:', labelBefore, '=>', labelAfter);
  // Open Server Files dialog
  const serverBtn = await page.evaluateHandle(() => Array.from(document.querySelectorAll('button')).find(b=>/Server Files/i.test(b.textContent||'')));
  if (serverBtn){ await serverBtn.asElement().click(); await wait(200); }
  const dlg = await page.$('[role="dialog"]');
  console.log('Server dialog present:', !!dlg);
  // Verify left rail shows page thumb label style (P.1)
  const hasP1 = await page.evaluate(()=>{
    return !!Array.from(document.querySelectorAll('button')).find(b=>/P\.\s*1/.test(b.textContent||''));
  });
  console.log('Left rail thumb present:', !!hasP1);
  await browser.close();
  console.log('UX smoke: OK');
})();
