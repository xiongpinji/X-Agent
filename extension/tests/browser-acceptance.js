const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { chromium } = require('playwright-core')
const { PACKAGE_FILES } = require('../scripts/package-extension')

const ROOT = path.resolve(__dirname, '..')
const BROWSER = process.env.XAGENT_CHROME_PATH || chromium.executablePath()

async function main() {
  if (!fs.existsSync(BROWSER)) throw new Error('Chromium executable is unavailable')
  const temporaryRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'xagent-extension-browser-'))
  const extensionRoot = path.join(temporaryRoot, 'extension')
  const profileRoot = path.join(temporaryRoot, 'profile')
  fs.mkdirSync(extensionRoot)
  for (const name of PACKAGE_FILES) {
    const target = path.join(extensionRoot, name)
    fs.mkdirSync(path.dirname(target), { recursive: true })
    fs.copyFileSync(path.join(ROOT, name), target)
  }

  let context
  try {
    context = await chromium.launchPersistentContext(profileRoot, {
      executablePath: BROWSER,
      headless: false,
      args: [
        `--disable-extensions-except=${extensionRoot}`,
        `--load-extension=${extensionRoot}`,
        '--disable-default-apps',
        '--no-first-run',
        '--window-position=-32000,-32000',
      ],
    })
    const extensionsPage = await context.newPage()
    await extensionsPage.goto('chrome://extensions/')
    const extensionId = await extensionsPage.waitForFunction(() => {
      const manager = document.querySelector('extensions-manager')
      const list = manager?.shadowRoot?.querySelector('extensions-item-list')
      const items = list?.shadowRoot?.querySelectorAll('extensions-item') || []
      for (const item of items) {
        if (item.data?.name === 'X-Agent Runner') return item.data.id
      }
      return undefined
    }, undefined, { timeout: 15_000 }).then((handle) => handle.jsonValue())
    if (typeof extensionId !== 'string' || !extensionId) throw new Error('Extension ID was not discovered')

    const popup = await context.newPage()
    const pageErrors = []
    popup.on('pageerror', (error) => pageErrors.push(error.message))
    popup.on('console', (message) => {
      if (message.type() === 'error') pageErrors.push(message.text())
    })
    await popup.goto(`chrome-extension://${extensionId}/popup.html`)
    await popup.locator('#login-form').waitFor()
    await popup.locator('#run-form').waitFor({ state: 'attached' })
    const result = await popup.evaluate(() => ({
      runtimeId: chrome.runtime.id,
      title: document.title,
      hasInlineScripts: document.querySelectorAll('script:not([src])').length > 0,
      hasPasswordField: document.querySelector('#password')?.getAttribute('type') === 'password',
    }))
    if (result.runtimeId !== extensionId) throw new Error('Runtime extension ID mismatch')
    if (result.title !== 'X-Agent Runner') throw new Error('Unexpected popup title')
    if (result.hasInlineScripts) throw new Error('Popup contains inline scripts')
    if (!result.hasPasswordField) throw new Error('Password field is not protected')
    if (pageErrors.length > 0) throw new Error(`Popup emitted errors: ${pageErrors.join('; ')}`)
    process.stdout.write(`${JSON.stringify({ status: 'passed', extensionId, ...result })}\n`)
  } finally {
    await context?.close()
    fs.rmSync(temporaryRoot, { recursive: true, force: true })
  }
}

main().catch((error) => {
  process.stderr.write(`${error.message}\n`)
  process.exitCode = 1
})
