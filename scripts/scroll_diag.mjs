import { connect } from 'puppeteer';

const BASE = process.env.BASE_URL || 'http://127.0.0.1:8080/main';
const DISCOVERY = process.env.BROWSERLESS_DISCOVERY_URL || 'http://127.0.0.1:3000/json/version';

async function getWS() {
  try {
    const res = await fetch(DISCOVERY);
    const j = await res.json();
    if (j && j.webSocketDebuggerUrl) return j.webSocketDebuggerUrl.replace('0.0.0.0', '127.0.0.1');
  } catch {}
  return 'ws://127.0.0.1:3000';
}

(async () => {
  const ws = await getWS();
  const browser = await connect({ browserWSEndpoint: ws });
  const page = await browser.newPage();
  await page.goto(BASE, { waitUntil: 'domcontentloaded' });
  const info = await page.evaluate(() => {
    const center = document.querySelector('[data-component="ClassicLayout.Center"]');
    if (!center) return { ok:false, reason:'no center' };
    const st = window.getComputedStyle(center);
    return {
      ok: true,
      styles: { overflow: st.overflow, overflowY: st.overflowY, minHeight: st.minHeight },
      dims: { clientHeight: center.clientHeight, scrollHeight: center.scrollHeight, scrollTop: center.scrollTop }
    };
  });
  console.log(JSON.stringify(info, null, 2));
  await browser.disconnect();
})();

