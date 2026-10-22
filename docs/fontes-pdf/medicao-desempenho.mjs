// Lightweight stand-in for Lighthouse (not installable here): load metrics and basic
// accessibility checks of the production-like build, on a phone-sized viewport.
// Usage: node medicao-desempenho.mjs
import puppeteer from 'puppeteer-core'

const BASE = process.env.SENTINELA_URL ?? 'https://localhost:8443'
const PAGES = ['/', '/registrar', '/prevencao', '/entrar', '/acompanhar']

const browser = await puppeteer.launch({
  executablePath: process.env.BROWSER_PATH ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
  acceptInsecureCerts: true,
  args: ['--no-first-run', '--lang=pt-BR'],
})

for (const path of PAGES) {
  // A fresh context per page: cold cache, like a first visit.
  const ctx = await browser.createBrowserContext()
  const page = await ctx.newPage()
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true })
  const cdp = await page.createCDPSession()
  await cdp.send('Network.enable')
  // Slow 4G-like profile, same order of magnitude as Lighthouse's mobile throttling.
  await cdp.send('Network.emulateNetworkConditions', {
    offline: false,
    latency: 150,
    downloadThroughput: (1.6 * 1024 * 1024) / 8,
    uploadThroughput: (750 * 1024) / 8,
  })
  let bytes = 0
  cdp.on('Network.loadingFinished', (e) => (bytes += e.encodedDataLength))
  await page.evaluateOnNewDocument(() => {
    window.__lcp = 0
    new PerformanceObserver((list) => {
      for (const e of list.getEntries()) window.__lcp = e.startTime
    }).observe({ type: 'largest-contentful-paint', buffered: true })
  })
  await page.goto(BASE + path, { waitUntil: 'networkidle2', timeout: 60000 })
  const r = await page.evaluate(() => {
    const nav = performance.getEntriesByType('navigation')[0]
    const fcp = performance.getEntriesByName('first-contentful-paint')[0]?.startTime ?? 0
    const labelled = (el) =>
      el.getAttribute('aria-label') ||
      el.getAttribute('aria-labelledby') ||
      el.closest('label') ||
      (el.id && document.querySelector(`label[for="${el.id}"]`))
    const fields = [...document.querySelectorAll('input:not([type=hidden]), select, textarea')]
    const buttons = [...document.querySelectorAll('button, a[href]')]
    return {
      fcp: Math.round(fcp),
      lcp: Math.round(window.__lcp),
      load: Math.round(nav.loadEventEnd),
      lang: document.documentElement.lang,
      title: document.title,
      fieldsWithoutLabel: fields.filter((f) => !labelled(f)).length,
      fields: fields.length,
      controlsWithoutName: buttons.filter((b) => !(b.textContent.trim() || b.getAttribute('aria-label') || b.title)).length,
      imagesWithoutAlt: [...document.querySelectorAll('img')].filter((i) => !i.hasAttribute('alt') && !i.closest('.leaflet-pane')).length,
      h1: document.querySelectorAll('h1').length,
    }
  })
  console.log(
    `${path.padEnd(12)} FCP ${r.fcp} ms · LCP ${r.lcp} ms · load ${r.load} ms · ${(bytes / 1024).toFixed(0)} KiB` +
      ` · lang=${r.lang} · campos sem rótulo ${r.fieldsWithoutLabel}/${r.fields}` +
      ` · botões/links sem nome ${r.controlsWithoutName} · imagens sem alt ${r.imagesWithoutAlt} · h1 ${r.h1}`,
  )
  await ctx.close()
}
await browser.close()
