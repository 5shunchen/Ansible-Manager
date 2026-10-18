/**
 * e2e 共享 helper：无头浏览器启动、登录、结果收集。
 * 用法：node e2e/tests/xxx.mjs
 */
import { chromium } from 'playwright'

export const BASE = process.env.E2E_BASE_URL || 'http://192.168.31.114:3000'
export const TEST_HOST = { ip: '192.168.31.26', port: 22, username: 'root', password: '123' }

/** 无头浏览器启动（不依赖 x11/图形界面）。
 *  显式剔除 DISPLAY 环境变量，避免继承父 shell 的 X11 转发（localhost:10.0）
 *  导致浏览器去尝试连远程 x11 server 而产生转发请求。 */
export async function launchBrowser() {
  return chromium.launch({
    headless: true,
    env: { ...process.env, DISPLAY: '' },
  })
}

/** 用主机密码登录，返回 (page, browser) */
export async function login(browser, host = TEST_HOST) {
  const page = await browser.newPage()
  await page.goto(`${BASE}/login`)
  await page.fill('input[placeholder="主机 IP"]', host.ip)
  await page.fill('input[placeholder="主机密码"]', host.password)
  await page.click('button:has-text("登 录")')
  await page.waitForTimeout(3500)
  if (page.url().includes('/login')) {
    throw new Error('登录失败：仍停留在登录页')
  }
  return page
}

/** 结果收集器 */
export class Reporter {
  constructor() {
    this.results = []
  }
  pass(name, detail = '') {
    this.results.push({ name, ok: true, detail })
    console.log(`PASS  ${name}  ${detail}`)
  }
  fail(name, detail = '') {
    this.results.push({ name, ok: false, detail })
    console.log(`FAIL  ${name}  ${detail}`)
  }
  summary() {
    const failed = this.results.filter((r) => !r.ok)
    console.log(`\n===== 汇总: ${this.results.length - failed.length}/${this.results.length} 通过 =====`)
    return failed.length
  }
}
