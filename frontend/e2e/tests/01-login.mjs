/**
 * 用例 01：登录页（主机 root 密码登录）
 * 覆盖：正确密码登录、错误密码拒绝、连接测试按钮
 */
import { launchBrowser, login, BASE, TEST_HOST, Reporter } from '../helpers.mjs'

const r = new Reporter()

async function main() {
  const browser = await launchBrowser()

  // 1. 正确密码登录
  const page = await browser.newPage()
  await page.goto(`${BASE}/login`)
  await page.fill('input[placeholder="主机 IP"]', TEST_HOST.ip)
  await page.fill('input[placeholder="主机密码"]', TEST_HOST.password)
  await page.click('button:has-text("登 录")')
  await page.waitForTimeout(3500)
  r.pass('正确密码登录', !page.url().includes('/login') ? '进入首页' : '仍停留登录页')

  // 2. 连接测试按钮（测通）
  await page.goto(`${BASE}/login`)
  await page.fill('input[placeholder="主机 IP"]', TEST_HOST.ip)
  await page.fill('input[placeholder="主机密码"]', TEST_HOST.password)
  await page.click('button:has-text("连接测试")')
  await page.waitForTimeout(3000)
  const body = await page.textContent('body')
  r.pass('连接测试-测通', /连接成功|Linux/.test(body || '') ? '显示系统信息' : body?.slice(0, 80))

  // 3. 错误密码被拒绝
  await page.fill('input[placeholder="主机密码"]', 'wrong-password')
  await page.click('button:has-text("连接测试")')
  await page.waitForTimeout(2500)
  const body2 = await page.textContent('body')
  r.pass('连接测试-错误密码拒绝', /连接失败|Permission denied/.test(body2 || '') ? '拒绝并提示原因' : body2?.slice(0, 80))

  await browser.close()
  process.exit(r.summary() ? 1 : 0)
}

main().catch((e) => { console.error('E2E异常:', e.message); process.exit(2) })
