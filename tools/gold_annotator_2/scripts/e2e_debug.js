// Minimal E2E: connect to browserless, load the app, upload sample PDF, draw a box, and assert overlay exists.
const puppeteer = require('puppeteer-core');

async function run() {
  const WS = process.env.BROWSERLESS_WS || 'ws://localhost:3000?token=changeme';
  const APP = process.env.APP_URL || 'http://host.docker.internal:3002';
  const PDF = process.env.SAMPLE_PDF || __dirname + '/../data/sample.pdf';
  const browser = await puppeteer.connect({ browserWSEndpoint: WS });
  const page = await browser.newPage();
  page.setDefaultTimeout(15000);
  await page.goto(APP, { waitUntil: 'networkidle2' });
  const initialCanvas = await page.evaluate(() => document.querySelectorAll('canvas').length);
  console.log('initial canvas:', initialCanvas);

  // Use the sample loader to avoid file dialog UX
  const loadBtn = await page.waitForSelector('[data-testid="load-sample"]');
  await loadBtn.click();

  // wait for canvas to render
  await page.waitForSelector('canvas', { timeout: 30000 });
  const afterInputCanvas = await page.evaluate(() => document.querySelectorAll('canvas').length);
  console.log('after input canvas count:', afterInputCanvas);
  await page.waitForFunction(() => {
    const c = document.querySelector('canvas');
    return c && c.width > 0 && c.height > 0;
  }, { timeout: 30000 });

  // Get overlay rect to compute drag coords
  await page.waitForSelector('[data-testid="overlay"]', { timeout: 15000 });
  const overlayBox = await page.evaluate(() => {
    const svg = document.querySelector('[data-testid="overlay"]');
    if (!svg) return null;
    const r = svg.getBoundingClientRect();
    return { x: r.x, y: r.y, w: r.width, h: r.height };
  });
  if (!overlayBox) throw new Error('overlay SVG not found');

  const start = { x: overlayBox.x + 50, y: overlayBox.y + 50 };
  const end = { x: start.x + 120, y: start.y + 80 };

  await page.mouse.move(start.x, start.y);
  await page.mouse.down();
  await page.mouse.move(end.x, end.y, { steps: 15 });
  await page.mouse.up();

  // count boxes
  const count = await page.evaluate(() => document.querySelectorAll('svg g[data-boxid] rect[data-boxid]').length || document.querySelectorAll('svg g rect[data-boxid]').length || document.querySelectorAll('svg rect[data-boxid]').length);
  console.log('boxes:', count);

  // Screenshot for record
  await page.screenshot({ path: '/tmp/ga2_after_draw.png' });
  await browser.close();
  if (count < 1) throw new Error('No boxes detected after draw');
}

run().catch((e) => {
  console.error('E2E failed:', e);
  process.exit(1);
});
