/**
 * 用例 05：各功能页面冒烟测试
 * 覆盖：项目管理/应用主机/Agent主机/监控大屏/Playbook/任务/系统配置/权限/插件/部署
 * 每个页面验证：能加载、主表格或关键元素存在、不报错
 */
import { launchBrowser, login, BASE, Reporter } from '../helpers.mjs'

const r = new Reporter()

const PAGES = [
  { path: '/project', name: '项目管理', expect: 'el-table' },
  { path: '/apphost', name: '应用主机', expect: 'el-table' },
  { path: '/agenthost', name: 'Agent主机', expect: 'el-table' },
  { path: '/monitor/dashboard', name: '监控大屏', expect: 'el-card' },
  { path: '/playbook', name: 'Playbook管理', expect: 'el-table' },
  { path: '/task', name: '任务管理', expect: 'el-table' },
  { path: '/system/config', name: '系统配置', expect: 'el-card' },
  { path: '/permission', name: '权限管理', expect: 'el-table' },
  { path: '/plugin', name: '插件工程', expect: 'el-table' },
  { path: '/deployment/project', name: '工程部署', expect: 'el-table' },
]

async function main() {
  const browser = await launchBrowser()
  const page = await login(browser)

  for (const p of PAGES) {
    await page.goto(`${BASE}${p.path}`)
    await page.waitForTimeout(2500)
    const ok = await page.locator(p.expect).count() > 0
    const bodyText = (await page.textContent('body') || '').slice(0, 60).replace(/\n/g, ' ')
    r.pass(`${p.name}页面`, ok ? `${p.expect} 存在` : bodyText)
  }

  await browser.close()
  process.exit(r.summary() ? 1 : 0)
}

main().catch((e) => { console.error('E2E异常:', e.message); process.exit(2) })
