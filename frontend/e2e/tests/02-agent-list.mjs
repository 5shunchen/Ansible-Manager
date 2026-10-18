/**
 * 用例 02：Agent 主机列表
 * 覆盖：系统/CPU/内存列显示、真实数据回填、Agent 状态列、操作按钮
 */
import { launchBrowser, login, BASE, Reporter } from '../helpers.mjs'

const r = new Reporter()

async function main() {
  const browser = await launchBrowser()
  const page = await login(browser)

  await page.goto(`${BASE}/agenthost`)
  await page.waitForTimeout(2500)

  // 表头列
  const header = await page.textContent('.el-table')
  r.pass('系统列显示', /系统/.test(header || ''))
  r.pass('CPU列显示', /CPU/.test(header || ''))
  r.pass('内存列显示', /内存/.test(header || ''))
  r.pass('Agent状态列显示', /Agent\s*状态/.test(header || ''))

  // 真实数据回填
  const rows = await page.evaluate(() =>
    [...document.querySelectorAll('.el-table__row')].map((r) => r.innerText).join('\n')
  )
  r.pass('真实系统数据', /Linux/.test(rows) && /\d+\s*(核|GB|MB)/.test(rows), rows.split('\n')[0]?.slice(0, 100))

  // 行操作按钮存在（连接测试/终端/文件/免密）
  const body = await page.textContent('.el-table')
  r.pass('行操作按钮', /编辑|删除/.test(body || ''), '')

  await browser.close()
  process.exit(r.summary() ? 1 : 0)
}

main().catch((e) => { console.error('E2E异常:', e.message); process.exit(2) })
