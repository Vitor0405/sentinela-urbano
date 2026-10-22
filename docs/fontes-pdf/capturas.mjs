// Captures the app screens used by the article. Requires `docker compose up` (dev seed data).
// Usage: npm run capturas
import { mkdirSync } from 'node:fs'
import puppeteer from 'puppeteer-core'

const BASE = process.env.SENTINELA_URL ?? 'http://localhost:5173'
const PASSWORD = process.env.SEED_PASSWORD ?? 'sentinela123'
const OUT = new URL('./capturas/', import.meta.url).pathname.replace(/^\/(\w:)/, '$1')
mkdirSync(OUT, { recursive: true })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await puppeteer.launch({
  executablePath: process.env.BROWSER_PATH ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
  args: ['--no-first-run', '--lang=pt-BR'],
})

async function open(viewport, mobile = false, email = null) {
  // A fresh incognito-like context per persona, so sessions never leak between shots.
  const context = await browser.createBrowserContext()
  const page = await context.newPage()
  await page.setViewport({ ...viewport, deviceScaleFactor: 2, isMobile: mobile, hasTouch: mobile })
  if (email) {
    await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' })
    await page.evaluate(
      async (email, password) => {
        const r = await fetch('/api/auth/login', {
          method: 'POST',
          headers: { 'content-type': 'application/json' },
          body: JSON.stringify({ email, password }),
        })
        const d = await r.json()
        localStorage.setItem('sentinela.session', JSON.stringify({ token: d.access_token, user: d.user }))
      },
      email,
      PASSWORD,
    )
  }
  return { page, context }
}

async function shot(page, path, name, { wait = 2500, fullPage = false } = {}) {
  await page.goto(BASE + path, { waitUntil: 'networkidle2', timeout: 60000 })
  await sleep(wait)
  await page.screenshot({ path: OUT + name, fullPage })
  console.log('✓', name)
}

const desktop = { width: 1280, height: 760 }
const phone = { width: 390, height: 844 }

{
  const { page, context } = await open(desktop)
  await shot(page, '/', 'map-public.png', { wait: 3500 })
  await context.close()
}
{
  const { page, context } = await open(phone, true)
  await page.goto(BASE + '/registrar', { waitUntil: 'networkidle2' })
  await sleep(1500)
  await page.evaluate(() => document.querySelectorAll('.type-card')[0].click())
  const map = await page.$('.picker-map')
  await map.evaluate((el) => el.scrollIntoView({ block: 'center' }))
  await sleep(800)
  const box = await map.boundingBox()
  await page.mouse.click(box.x + box.width / 2 + 20, box.y + box.height / 2 - 10)
  await sleep(1200)
  await page.evaluate(() => {
    const step = document.querySelectorAll('.step')[2]
    window.scrollTo(0, step.getBoundingClientRect().top + window.scrollY - 64)
  })
  await sleep(1500)
  await page.screenshot({ path: OUT + 'report-location.png' })
  console.log('✓ report-location.png')
  await context.close()
}
{
  const { page, context } = await open(desktop, false, 'agente@sentinela.test')
  await shot(page, '/fila', 'queue.png')
  await context.close()
}
{
  const { page, context } = await open({ width: 1280, height: 900 }, false, 'gestor@sentinela.test')
  await shot(page, '/liraa', 'liraa.png', { fullPage: true })
  await context.close()
}
{
  const { page, context } = await open(phone, true, 'morador@sentinela.test')
  // Overdue occurrence of the seed resident, and one awaiting the resident's answer.
  const [overdue, awaiting] = await page.evaluate(async () => {
    const r = await fetch('/api/occurrences/mine', {
      headers: { Authorization: `Bearer ${JSON.parse(localStorage.getItem('sentinela.session')).token}` },
    })
    const items = (await r.json()).items
    return [
      items.find((i) => i.response_overdue)?.protocol,
      items.find((i) => i.status === 'resolvida_pelo_agente')?.protocol,
    ]
  })
  if (overdue) await shot(page, `/acompanhar/${overdue}`, 'tracking-overdue.png', { wait: 1500 })
  if (awaiting) await shot(page, `/acompanhar/${awaiting}`, 'question.png', { wait: 1500 })
  await context.close()
}

await browser.close()
