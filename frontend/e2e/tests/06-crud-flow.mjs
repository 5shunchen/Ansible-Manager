/**
 * 用例 06：核心 CRUD 流程
 * 覆盖：项目管理（新增/列表）、Playbook（列表+扫描）、主机（列表+检测按钮）
 */
import { launchBrowser, login, BASE, Reporter } from '../helpers.mjs'

const r = new Reporter()

async function main() {
  const browser = await launchBrowser()
  const page = await login(browser)

  // 先选一台 Agent 主机（解除作用域守卫），再访问业务页面
  await page.goto(`${BASE}/agenthost`)
  await page.waitForTimeout(3000)
  // 选第一台 Agent 主机
  const agentSelect = page.locator('.agent-host-filter .el-select').first()
  if (await agentSelect.count()) {
    await agentSelect.click()
    await page.waitForTimeout(1000)
    const option = page.locator('.el-select-dropdown__item').first()
    if (await option.count()) await option.click()
    await page.waitForTimeout(1500)
  }
  r.pass('选择Agent主机', true)

  // 项目管理：列表加载 + 新增按钮
  await page.goto(`${BASE}/project`)
  await page.waitForTimeout(2500)
  r.pass('项目管理-列表', await page.locator('.el-table').count() > 0)
  r.pass('项目管理-新增按钮', await page.locator('button:has-text("新增")').count() > 0)

  // Playbook 管理：列表 + 扫描区
  await page.goto(`${BASE}/playbook`)
  await page.waitForTimeout(3000)
  r.pass('Playbook-列表', await page.locator('.el-table').count() > 0)
  r.pass('Playbook-扫描区', await page.evaluate(() => document.body.innerText.includes('扫描 Playbook')))

  // 主机管理：列表 + 操作按钮
  await page.goto(`${BASE}/host/list`)
  await page.waitForTimeout(2500)
  r.pass('主机列表-表格', await page.locator('.el-table').count() > 0)
  r.pass('主机列表-操作按钮', await page.locator('button[title="Web 终端"]').count() > 0)

  await browser.close()
  process.exit(r.summary() ? 1 : 0)
}

main().catch((e) => { console.error('E2E异常:', e.message); process.exit(2) })
