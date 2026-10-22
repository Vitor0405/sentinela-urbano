// Phase 5 check against the production-like stack (docker-compose.prod.yml):
// installable PWA, offline start, CSP, password reset and agent invitation via Mailpit.
// Usage: node verifica-fase5.mjs
import { mkdirSync } from 'node:fs'
import puppeteer from 'puppeteer-core'

const BASE = process.env.SENTINELA_URL ?? 'https://localhost:8443'
const MAILPIT = process.env.MAILPIT_URL ?? 'http://localhost:8026'
const OUT = new URL('./capturas/', import.meta.url).pathname.replace(/^\/(\w:)/, '$1')
mkdirSync(OUT, { recursive: true })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await puppeteer.launch({
  executablePath: process.env.BROWSER_PATH ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
  acceptInsecureCerts: true, // Caddy's local CA is not installed in this browser
  args: ['--no-first-run', '--lang=pt-BR'],
})

const problems = []
const INVITED = `convidada-${Date.now()}@sentinela.test`
function watch(page, label) {
  page.on('console', (m) => {
    const text = m.text()
    if (m.type() === 'error' && /Content Security Policy|Refused to/.test(text)) problems.push(`${label}: ${text}`)
  })
  page.on('pageerror', (e) => problems.push(`${label}: ${e.message}`))
}

async function lastMailTo(address, subjectPart) {
  for (let i = 0; i < 20; i++) {
    const list = await (await fetch(`${MAILPIT}/api/v1/search?query=${encodeURIComponent(`to:${address}`)}`)).json()
    const msg = list.messages?.find((m) => m.Subject.includes(subjectPart))
    if (msg) {
      const full = await (await fetch(`${MAILPIT}/api/v1/message/${msg.ID}`)).json()
      return full.Text
    }
    await sleep(500)
  }
  throw new Error(`e-mail não chegou para ${address}`)
}

async function login(page, email, password = 'sentinela123') {
  await page.goto(BASE + '/entrar', { waitUntil: 'networkidle2' })
  await page.type('input[type=email]', email)
  await page.type('input[type=password]', password)
  await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle2' }), page.click('button[type=submit]')])
}

// --- 1. Installable PWA and offline start -------------------------------------------
{
  const ctx = await browser.createBrowserContext()
  const page = await ctx.newPage()
  watch(page, 'mapa')
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true })
  await page.goto(BASE + '/', { waitUntil: 'networkidle2' })
  const pwa = await page.evaluate(async () => {
    const reg = await navigator.serviceWorker.ready
    const manifest = await (await fetch(document.querySelector('link[rel=manifest]').href)).json()
    return { sw: !!reg.active, name: manifest.name, display: manifest.display, icons: manifest.icons.length }
  })
  console.log('PWA:', JSON.stringify(pwa))
  await sleep(1500)
  await page.setOfflineMode(true)
  await page.goto(BASE + '/registrar', { waitUntil: 'domcontentloaded' }).catch(() => {})
  await sleep(2000)
  const offlineTitle = await page.$eval('h1', (h) => h.textContent).catch(() => '(nada)')
  const types = await page.$$eval('.type-card', (c) => c.length)
  console.log(`offline (app fechado e reaberto sem rede): "${offlineTitle}", ${types} tipos de risco do cache`)
  await page.screenshot({ path: OUT + 'f5-offline-pwa.png' })
  await page.setOfflineMode(false)
  await ctx.close()
}

// --- 2. Forgot password → e-mail → new password → logged in ------------------------
{
  const ctx = await browser.createBrowserContext()
  const page = await ctx.newPage()
  watch(page, 'senha')
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true })
  await page.goto(BASE + '/esqueci-senha', { waitUntil: 'networkidle2' })
  await page.type('input[type=email]', 'vizinha2@sentinela.test')
  await page.click('button[type=submit]')
  await sleep(1000)
  const text = await lastMailTo('vizinha2@sentinela.test', 'Redefinição de senha')
  const link = text.match(/https:\/\/\S+nova-senha#\S+/)[0]
  await page.goto(link, { waitUntil: 'networkidle2' })
  const pw = await page.$$('input[type=password]')
  await pw[0].type('senha-nova-da-vizinha')
  await pw[1].type('senha-nova-da-vizinha')
  await Promise.all([page.waitForNavigation({ waitUntil: 'networkidle2' }), page.click('button[type=submit]')])
  const session = await page.evaluate(() => JSON.parse(localStorage.getItem('sentinela.session') ?? 'null')?.user?.email)
  console.log('redefinição de senha: logada como', session)
  await page.goto(BASE + '/conta', { waitUntil: 'networkidle2' })
  await sleep(800)
  await page.screenshot({ path: OUT + 'f5-conta.png', fullPage: true })
  await ctx.close()
}

// --- 3. Manager: invite an agent, who sets the password from the e-mail ------------
{
  const ctx = await browser.createBrowserContext()
  const page = await ctx.newPage()
  watch(page, 'gestao')
  await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 2 })
  await login(page, 'gestor@sentinela.test')
  await page.goto(BASE + '/equipe', { waitUntil: 'networkidle2' })
  await sleep(800)
  const inputs = await page.$$('form input')
  await inputs[0].type('Agente Convidada')
  await inputs[1].type(INVITED)
  await page.evaluate(() => [...document.querySelectorAll('button')].find((b) => b.textContent.includes('Enviar convite')).click())
  await sleep(1500)
  console.log('convite:', await page.$eval('.alert', (a) => a.textContent).catch(() => '(sem mensagem)'))
  await page.screenshot({ path: OUT + 'f5-equipe.png' })
  await page.goto(BASE + '/configuracoes', { waitUntil: 'networkidle2' })
  await sleep(1000)
  await page.screenshot({ path: OUT + 'f5-configuracoes.png' })
  await ctx.close()

  const ctx2 = await browser.createBrowserContext()
  const agent = await ctx2.newPage()
  watch(agent, 'convite')
  await agent.setViewport({ width: 1280, height: 900, deviceScaleFactor: 2 })
  const invite = await lastMailTo(INVITED, 'Convite para a equipe')
  await agent.goto(invite.match(/https:\/\/\S+nova-senha#\S+/)[0], { waitUntil: 'networkidle2' })
  console.log('tela do convite:', await agent.$eval('h1', (h) => h.textContent))
  const pw = await agent.$$('input[type=password]')
  await pw[0].type('senha-da-convidada')
  await pw[1].type('senha-da-convidada')
  await Promise.all([agent.waitForNavigation({ waitUntil: 'networkidle2' }), agent.click('button[type=submit]')])
  await sleep(1500)
  console.log('agente convidada caiu em:', new URL(agent.url()).pathname, '| itens na fila:', await agent.$$eval('.queue-item', (q) => q.length))
  await ctx2.close()
}

await browser.close()
console.log('violações de CSP / erros de página:', problems.length ? problems : 'nenhum')
