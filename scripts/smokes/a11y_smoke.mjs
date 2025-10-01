/* eslint-disable no-console */
import puppeteer from "puppeteer";
import { createRequire } from "module";
const require = createRequire(import.meta.url);

const TARGET_URL = process.env.TARGET_URL || "http://127.0.0.1:4173/main";
const PREVIEW = process.env.VITE_PREVIEW === "1" || process.env.PREVIEW === "1";
const SEVERITY_ORDER = ["minor","moderate","serious","critical"];
const SEVERITY_MIN = (process.env.A11Y_SEVERITY_MIN || (PREVIEW ? "minor" : "serious")).toLowerCase();
const FAIL_INDEX = SEVERITY_ORDER.indexOf(SEVERITY_MIN);

function shouldFail(impact){
  const idx = SEVERITY_ORDER.indexOf((impact||"").toLowerCase());
  return idx >= 0 && idx >= FAIL_INDEX;
}

async function main(){
  const browser = await puppeteer.launch({ headless: true, args:["--no-sandbox","--disable-dev-shm-usage"]});
  const page = await browser.newPage();
  await page.goto(TARGET_URL, { waitUntil: "networkidle0", timeout: 30000 });
  await page.waitForSelector('[data-testid="page-label"]', { timeout: 30000 });
  await page.waitForFunction(() => !!(document.getElementById("root")?.childElementCount), { timeout: 30000 });

  await page.addScriptTag({ path: require.resolve("axe-core/axe.min.js") });
  const results = await page.evaluate(async () => await axe.run(document, { resultTypes: ["violations"] }));
  const violations = results.violations || [];
  for(const v of violations){
    console.log(`[a11y] ${v.id} impact=${v.impact} nodes=${v.nodes?.length ?? 0} help=${v.help}`);
  }
  const failing = violations.filter(v => shouldFail(v.impact));
  if (!PREVIEW && failing.length){
    console.error(`[a11y] FAIL: ${failing.length} violations at impact >= ${SEVERITY_MIN}`);
    process.exit(1);
  }
  console.log(`[a11y] ok (preview=${PREVIEW}, violations=${violations.length}, failing=${failing.length})`);
  await browser.close();
}

main().catch(e => { console.error(e); process.exit(2); });
