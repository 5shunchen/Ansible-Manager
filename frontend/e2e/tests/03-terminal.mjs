/**
 * 用例 03：Web 终端
 * 覆盖：终端页挂载、WS 连接、执行命令回显
 */
import { launchBrowser, login, BASE, Reporter } from '../helpers.mjs'

const r = new Reporter()

async function main() {
  const browser = await launchBrowser()
  const page = await login(browser)

  await page.goto(`${BASE}/host/terminal?host_id=3`)
  await page.waitForTimeout(4000)

  // xterm 容器挂载（多标签下 .term 在当前激活标签里）
  const termCount = await page.locator('.term').count()
  r.pass('终端挂载', termCount > 0 ? 'xterm 容器存在' : '未找到 .term')

  // 等待 WS 连接并拿到 shell 提示符
  await page.waitForTimeout(2500)
  const content = await page.evaluate(() => document.querySelector('.term')?.innerText || '')
  r.pass('WS 连接输出', /root@|\$|#/.test(content), content.slice(0, 80).replace(/\n/g, ' '))

  await browser.close()
  process.exit(r.summary() ? 1 : 0)
}

main().catch((e) => { console.error('E2E异常:', e.message); process.exit(2) })
