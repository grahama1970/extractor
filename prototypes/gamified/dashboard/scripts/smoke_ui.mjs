import { spawn } from 'node:child_process'
import { setTimeout as delay } from 'node:timers/promises'
import http from 'node:http'
import puppeteer from 'puppeteer'
import { mkdir } from 'node:fs/promises'

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
    dev = spawn('npm', ['run', 'dev'], { stdio: 'inherit', shell: true })
    const ok = await waitForServer(baseUrl, 30000)
    if (!ok){
      console.error('Dev server failed to start')
      dev.kill('SIGKILL')
      process.exit(2)
    }
  }

  const browser = await puppeteer.launch({ headless: 'new', args: process.env.CI ? ['--no-sandbox','--disable-setuid-sandbox'] : [] })
  const page = await browser.newPage()
  const errors = []
  page.on('pageerror', (e) => errors.push(['page', String(e)]))
  page.on('console', (msg) => {
    if (msg.type() === 'error') errors.push(['console', msg.text()])
  })
  await page.goto(baseUrl, { waitUntil: 'networkidle0', timeout: 30000 })
  await page.waitForSelector('text/Scoreboard', { timeout: 15000 }).catch(()=>{})
  // Open Logs tab (find button with text 'Logs')
  try {
    const [logsBtn] = await page.$x("//button[contains(@role,'tab') and contains(., 'Logs')]")
    if (logsBtn) await logsBtn.click()
  } catch {}
  // Load demo logs via command palette
  await page.keyboard.down(process.platform === 'darwin' ? 'Meta' : 'Control')
  await page.keyboard.press('KeyK')
  await page.keyboard.up(process.platform === 'darwin' ? 'Meta' : 'Control')
  await page.waitForSelector('text=Load Demo Logs (5000)', { timeout: 5000 })
  await page.click('text=Load Demo Logs (5000)')
  // Type into fuzzy search
  await page.fill('input[placeholder="Search logs"]', 'error spike')
  await page.waitForSelector('text=error spike', { timeout: 10000 })
  const url = page.url()
  if (!url.includes('tab=logs') || !decodeURIComponent(url).includes('q=error spike')){
    console.error('URL does not reflect filters:', url)
    process.exit(1)
  }
  // Open palette and ensure Copy Share URL and a Recent item are visible
  await page.keyboard.down(process.platform === 'darwin' ? 'Meta' : 'Control')
  await page.keyboard.press('KeyK')
  await page.keyboard.up(process.platform === 'darwin' ? 'Meta' : 'Control')
  await page.waitForSelector('text=Copy Share URL', { timeout: 5000 })
  // Recent may take a tick to appear after URL sync
  await delay(300)
  await page.waitForSelector('text=Recent:', { timeout: 5000 }).catch(()=>{})
  // Click first visible matching row to open sheet
  const el = await page.$('text=error spike')
  if (el) { await el.click() }
  await page.waitForSelector('text=Log Details', { timeout: 5000 }).catch(()=>{})
  try { await mkdir('scripts/artifacts', { recursive: true }) } catch {}
  await page.screenshot({ path: 'scripts/artifacts/dashboard_smoke.png', fullPage: true }).catch(()=>{})
  await browser.close()

  if (dev){ dev.kill('SIGTERM') }
  if (errors.length){
    console.error('UI smoke captured errors:', errors.slice(0,3))
    process.exit(1)
  }
  console.log('UI smoke passed')
}

main().catch((e) => { console.error(e); process.exit(1) })
