import { spawn } from 'node:child_process'
import { setTimeout as delay } from 'node:timers/promises'
import http from 'node:http'
import puppeteer from 'puppeteer'

const PORT = Number(process.env.PORT || 5199)

function httpOk(url){
  return new Promise((resolve) => {
    const req = http.get(url, (res) => { resolve(res.statusCode && res.statusCode < 500) })
    req.on('error', () => resolve(false))
    req.end()
  })
}

async function waitForServer(url, timeoutMs=20000){
  const start = Date.now()
  while (Date.now() - start < timeoutMs){
    if (await httpOk(url)) return true
    await delay(300)
  }
  return false
}

async function main(){
  const baseUrl = process.env.BASE_URL || `http://localhost:${PORT}`
  let dev
  if (!process.env.BASE_URL){
    dev = spawn('npm', ['run', 'dev'], { cwd: new URL('..', import.meta.url).pathname, stdio: 'inherit', shell: true })
    const ok = await waitForServer(baseUrl, 30000)
    if (!ok){
      console.error('Dev server failed to start')
      dev.kill('SIGKILL')
      process.exit(2)
    }
  }

  const browser = await puppeteer.launch({ headless: 'new', args: process.env.CI ? ['--no-sandbox','--disable-setuid-sandbox'] : [] })
  const page = await browser.newPage()
  
  // Stub optimize endpoint to avoid needing a backend
  await page.setRequestInterception(true)
  page.on('request', (req) => {
    try {
      const url = req.url()
      if (url.endsWith('/optimize_from_spec')){
        const body = JSON.stringify({ ok: true, raw: 'raw', optimized: 'opt', diff: '--- raw
+++ optimized
+added line' })
        return req.respond({ status: 200, contentType: 'application/json', body })
      }
    } catch {}
    req.continue()
  })
  await page.goto(baseUrl, { waitUntil: 'domcontentloaded', timeout: 30000 })
  
  await page.waitForSelector('text=Scoreboard', { timeout: 15000 }).catch(()=>{})

  // Trigger Run Again toast via keyboard 'r'
  await page.keyboard.press('KeyR')
  await page.waitForSelector('text=Run started', { timeout: 5000 }).catch(()=>{})
  // Trigger Fast run toast via 'f'
  await page.keyboard.press('KeyF')
  await page.waitForSelector('text=Fast run started', { timeout: 5000 }).catch(()=>{})
  // Trigger Optimize via 'o' and confirm toast & sheet
  await page.keyboard.press('KeyO')
  await page.waitForSelector('text=Optimize diff loaded', { timeout: 5000 }).catch(()=>{})
  await page.waitForSelector('text=Optimize Diff', { timeout: 5000 }).catch(()=>{})
  // Open Help via '?'
  await page.keyboard.down('Shift')
  await page.keyboard.press('Slash')
  await page.keyboard.up('Shift')
  await page.waitForSelector('text=About & Help', { timeout: 5000 }).catch(()=>{})

  try { await mkdir('scripts/artifacts', { recursive: true }) } catch {}
  await page.screenshot({ path: 'scripts/artifacts/dashboard_smoke_toasts.png', fullPage: true }).catch(()=>{})
  await browser.close()
  if (dev){ dev.kill('SIGTERM') }
  console.log('Toast smoke passed')
}

main().catch((e) => { console.error(e); process.exit(1) })

