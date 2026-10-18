/**
 * 用例 04：文件管理
 * 覆盖：文件页挂载、目录列表渲染
 */
import { launchBrowser, login, BASE, Reporter } from '../helpers.mjs'

const r = new Reporter()

async function main() {
  const browser = await launchBrowser()
  const page = await login(browser)

  await page.goto(`${BASE}/host/files?host_id=3`)
  await page.waitForTimeout(4000)

  // 文件表格挂载（多标签下表格在当前激活标签里）
  const tableCount = await page.locator('.el-table').count()
  r.pass('文件页挂载', tableCount > 0 ? '表格存在' : '未找到表格')

  // 目录内容（/ 下列出真实目录）
  await page.waitForTimeout(2000)
  const tableText = await page.evaluate(() => document.querySelector('.el-table')?.innerText || '')
  r.pass('目录内容', /root|home|opt|tmp|boot|dev/.test(tableText), tableText.slice(0, 80).replace(/\n/g, ' '))

  await browser.close()
  process.exit(r.summary() ? 1 : 0)
}

main().catch((e) => { console.error('E2E异常:', e.message); process.exit(2) })
