/**
 * 一键运行全部 e2e 用例（无头浏览器，不依赖 x11）。
 * 用法：node e2e/run-all.mjs
 */
import { execSync } from 'node:child_process'
import { readdirSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))
const testsDir = join(__dirname, 'tests')

const files = readdirSync(testsDir).filter((f) => f.endsWith('.mjs')).sort()
console.log(`发现 ${files.length} 个测试用例：${files.join(', ')}\n`)

let failed = 0
for (const f of files) {
  console.log(`========== 运行 ${f} ==========`)
  try {
    execSync(`node ${join(testsDir, f)}`, { stdio: 'inherit' })
  } catch {
    failed++
  }
  console.log('')
}
console.log(`===== 全部用例运行结束，失败 ${failed} 个 =====`)
process.exit(failed ? 1 : 0)
