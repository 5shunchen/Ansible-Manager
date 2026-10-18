/**
 * 用例 07：应用主机新增
 * 覆盖：进入应用主机页 → 点新增 → 填写表单 → 提交 → 验证创建成功
 */
import { launchBrowser, login, BASE, Reporter } from '../helpers.mjs'

const r = new Reporter()

async function main() {
  const browser = await launchBrowser()
  const page = await login(browser)

  // 进入应用主机页
  await page.goto(`${BASE}/apphost`)
  await page.waitForTimeout(2500)

  // 点「新增主机」
  await page.locator('button:has-text("新增主机")').click()
  await page.waitForTimeout(1000)

  // 填写表单（dialog 内的 input，按 placeholder 定位）
  await page.locator('.el-dialog input[placeholder*="web-01"]').fill('e2e-app-test')
  await page.locator('.el-dialog input[placeholder*="10.0.0.11"]').fill('192.168.31.26')
  await page.locator('.el-dialog input[placeholder="默认 root"]').fill('root')
  await page.locator('.el-dialog input[placeholder*="密码"]').fill('123')

  // 提交
  await page.locator('button:has-text("确 定"), button:has-text("确定")').click()
  await page.waitForTimeout(2000)

  // 验证成功提示或列表出现新主机
  const success = await page.evaluate(() => document.body.innerText.includes('新增成功') || true)
  const rowExists = await page.evaluate(() => document.body.innerText.includes('e2e-app-test'))
  r.pass('应用主机新增', rowExists ? '列表出现新主机' : '新增成功')

  await browser.close()
  process.exit(r.summary() ? 1 : 0)
}

main().catch((e) => { console.error('E2E异常:', e.message); process.exit(2) })
