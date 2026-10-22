// Phase 4 check in a real browser: offline report → automatic send when back online,
// plus screenshots of the new screens. Requires `docker compose up`.
// Usage: node verifica-fase4.mjs
import { mkdirSync, writeFileSync } from 'node:fs'
import puppeteer from 'puppeteer-core'

const BASE = process.env.SENTINELA_URL ?? 'http://localhost:5173'
const OUT = new URL('./capturas/', import.meta.url).pathname.replace(/^\/(\w:)/, '$1')
mkdirSync(OUT, { recursive: true })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await puppeteer.launch({
  executablePath: process.env.BROWSER_PATH ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
  args: ['--no-first-run', '--lang=pt-BR'],
})

async function loginAs(page, email) {
  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' })
  await page.evaluate(async (email) => {
    const r = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ email, password: 'sentinela123' }),
    })
    const d = await r.json()
    localStorage.setItem('sentinela.session', JSON.stringify({ token: d.access_token, user: d.user }))
  }, email)
}

// --- 1. Offline report on a phone ----------------------------------------------------
{
  const context = await browser.createBrowserContext()
  const page = await context.newPage()
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true })
  await page.goto(BASE + '/registrar', { waitUntil: 'networkidle2' })
  await sleep(1500) // types and served area are now cached for offline use

  await page.setOfflineMode(true)
  const photo = Buffer.from(
    await (await fetch(BASE + '/pwa-512.png')).arrayBuffer(), // any image will do
  )
  const tmp = OUT + '_tmp.png'
  writeFileSync(tmp, photo)
  const gallery = (await page.$$('input[type=file]'))[1]
  await gallery.uploadFile(tmp)
  await page.evaluate(() => document.querySelectorAll('.type-card')[0].click())
  const map = await page.$('.picker-map')
  await map.evaluate((el) => el.scrollIntoView({ block: 'center' }))
  await sleep(500)
  const box = await map.boundingBox()
  await page.mouse.click(box.x + box.width / 2, box.y + box.height / 2)
  await sleep(500)
  await page.evaluate(() => document.querySelector('button[type=submit]').click())
  await sleep(1500)
  const queuedTitle = await page.$eval('h1', (h) => h.textContent)
  const chip = await page.$eval('.pending-chip', (c) => c.textContent).catch(() => null)
  console.log('offline → tela:', queuedTitle, '| aviso no topo:', chip)
  await page.evaluate(() => window.scrollTo(0, 0))
  await page.screenshot({ path: OUT + 'f4-offline-guardado.png' })

  await page.goto(BASE + '/envios', { waitUntil: 'domcontentloaded' }).catch(() => {})
  await sleep(800)

  // Back online: the provider syncs on the "online" event.
  await page.setOfflineMode(false)
  await page.goto(BASE + '/envios', { waitUntil: 'networkidle2' })
  await sleep(3000)
  const status = await page.$$eval('.outbox-item', (els) => els.map((e) => e.innerText.replace(/\s+/g, ' ')))
  console.log('online → envios:', status)
  await page.screenshot({ path: OUT + 'f4-envios.png' })
  await context.close()
}

// --- 2. Prevention ------------------------------------------------------------------
{
  const context = await browser.createBrowserContext()
  const page = await context.newPage()
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true })
  await page.goto(BASE + '/prevencao', { waitUntil: 'networkidle2' })
  await sleep(1000)
  await page.screenshot({ path: OUT + 'f4-prevencao.png' })
  console.log('prevenção: seções', await page.$$eval('.prose h2', (h) => h.length))
  await context.close()
}

// --- 3. Agent route ----------------------------------------------------------------
{
  const context = await browser.createBrowserContext()
  await context.overridePermissions(BASE, ['geolocation'])
  const page = await context.newPage()
  await page.setViewport({ width: 1280, height: 860, deviceScaleFactor: 2 })
  await page.setGeolocation({ latitude: -16.7198, longitude: -43.8667, accuracy: 10 })
  await loginAs(page, 'agente@sentinela.test')
  await page.goto(BASE + '/rota', { waitUntil: 'networkidle2' })
  await page.evaluate(() => [...document.querySelectorAll('button')].find((b) => b.textContent.includes('localização')).click())
  await sleep(3500)
  const stops = await page.$$eval('.route-list li', (els) => els.length)
  console.log('rota: paradas', stops, '|', await page.$eval('.route-layout .hint', (h) => h.textContent).catch(() => ''))
  await page.screenshot({ path: OUT + 'f4-rota.png' })
  // remove the first stop
  await page.evaluate(() => document.querySelector('.route-list .icon-button').click())
  await sleep(2000)
  console.log('rota após remover 1: paradas', await page.$$eval('.route-list li', (els) => els.length))
  await context.close()
}

// --- 4. Manager: team scope and panel alerts -----------------------------------------
{
  const context = await browser.createBrowserContext()
  const page = await context.newPage()
  await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 2 })
  await loginAs(page, 'gestor@sentinela.test')
  await page.goto(BASE + '/equipe', { waitUntil: 'networkidle2' })
  await sleep(1500)
  await page.screenshot({ path: OUT + 'f4-equipe.png' })
  await page.goto(BASE + '/painel', { waitUntil: 'networkidle2' })
  await sleep(2500)
  const alertText = await page.$eval('.alerts', (e) => e.innerText.replace(/\s+/g, ' ')).catch(() => '')
  console.log('painel:', alertText.slice(0, 140))
  const el = await page.$('.alerts')
  if (el) await el.screenshot({ path: OUT + 'f4-alertas.png' })
  await context.close()
}

await browser.close()
