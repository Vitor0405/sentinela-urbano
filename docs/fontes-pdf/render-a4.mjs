// Usage: node render-a4.mjs <input.html> <output.pdf>
import puppeteer from 'puppeteer-core'

const [input, out] = process.argv.slice(2)
const here = new URL('.', import.meta.url)
const browser = await puppeteer.launch({
  executablePath: process.env.BROWSER_PATH ?? 'C:/Program Files/Google/Chrome/Application/chrome.exe',
  headless: true,
  args: ['--allow-file-access-from-files'],
})
const page = await browser.newPage()
await page.goto(new URL(input, here).href, { waitUntil: 'networkidle0' })
await page.evaluateHandle('document.fonts.ready')
const broken = await page.evaluate(() => [...document.images].filter((i) => !i.naturalWidth).length)
console.log('broken images:', broken)
await page.pdf({
  path: out,
  format: 'A4',
  printBackground: true,
  preferCSSPageSize: true,
  displayHeaderFooter: true,
  // ABNT: page number at the top right
  headerTemplate:
    '<div style="width:100%;font-size:10px;font-family:\'Times New Roman\',serif;text-align:right;padding:0 20mm 0 0;margin-top:12mm;"><span class="pageNumber"></span></div>',
  footerTemplate: '<span></span>',
})
await browser.close()
console.log('ok →', out)
