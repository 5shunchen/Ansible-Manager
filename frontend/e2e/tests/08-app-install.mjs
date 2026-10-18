/**
 * 用例 08：应用主机安装 App
 * 覆盖：进入应用主机页 → 点行内「装 App」→ 选 am-app 插件 → 提交 → 任务管理页能看到 app_install 任务 → 已装 App 抽屉出现记录
 */
import { launchBrowser, login, BASE, Reporter } from '../helpers.mjs'

const r = new Reporter()

async function main() {
  const browser = await launchBrowser()
  const page = await login(browser)

  await page.goto(`${BASE}/apphost`)
  await page.waitForTimeout(3000)

  // 找到 app-26 那一行
  const row = page.locator('tr', { hasText: 'app-26' })
  await row.waitFor()
  // 点行内「装 App」按钮
  await row.locator('button:has-text("装 App")').click()
  await page.waitForDialog?.()
  await page.waitForTimeout(1000)

  // 弹窗打开后选第一个插件
  const dialog = page.locator('.el-dialog:visible')
  await dialog.locator('.el-select').click()
  await page.waitForTimeout(500)
  await page.locator('.el-select-dropdown__item:visible').first().click()
  await page.waitForTimeout(300)
  // 提交
  await dialog.locator('button:has-text("开始安装")').click()
  await page.waitForTimeout(2000)

  // 应该跳到任务管理页
  if (page.url().includes('/task')) {
    r.pass('跳转到任务管理页', page.url())
  } else {
    r.fail('跳转任务管理页', page.url())
  }

  // 任务管理页需要先选 Agent 主机（scope guard）
  await page.locator('.agent-host-filter .el-select, header .el-select').first().click()
  await page.waitForTimeout(500)
  const opts = await page.locator('.el-select-dropdown__item:visible').all()
  if (opts.length) await opts[0].click()
  await page.waitForTimeout(2000)

  // 等任务完成
  await page.waitForTimeout(15000)
  const bodyText = await page.textContent('body')
  if (bodyText.includes('App安装')) {
    r.pass('任务列表出现 App安装 类型', '')
  } else {
    r.fail('任务列表没有 App安装 类型', bodyText.slice(-300))
  }

  // 回到应用主机页，打开「App 列表」抽屉验证
  await page.goto(`${BASE}/apphost`)
  await page.waitForTimeout(3000)
  const row2 = page.locator('tr', { hasText: 'app-26' })
  await row2.locator('button:has-text("App 列表")').click()
  await page.waitForTimeout(1500)
  const drawer = page.locator('.el-drawer:visible')
  const drawerText = await drawer.textContent()
  if (drawerText.includes('am-app')) {
    r.pass('抽屉里出现 am-app', '')
  } else {
    r.fail('抽屉里没有 am-app', drawerText.slice(0, 300))
  }

  await browser.close()
  process.exit(r.summary() ? 1 : 0)
}

main().catch((e) => { console.error('E2E异常:', e.message); process.exit(2) })
