// 临时验证脚本：确认动态菜单路由必须挂到 layout 子路由下。
// 运行：node check-routes.mjs
import { createRouter, createMemoryHistory } from 'vue-router'

const Layout = { name: 'LayoutStub', render: () => null }
const ViewStub = { name: 'ViewStub', render: () => null }

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/login', name: 'login', component: ViewStub },
      { path: '/', name: 'layout', component: Layout, children: [] },
      { path: '/:pathMatch(.*)*', name: '404', component: ViewStub },
    ],
  })
}

const menus = [
  { id: 1, path: '/project', name: '项目管理' },
  { id: 18, path: '/host', name: '主机管理', type: 'dir' },
  { id: 19, path: '/host/list', name: '主机列表' },
  { id: 24, path: '/agenthost', name: 'Agent主机' },
]

// ---- 旧写法：把路径 '/' 当父路由名传给 addRoute ----
const oldRouter = makeRouter()
for (const m of menus) {
  oldRouter.addRoute('/', { path: m.path, name: `menu-${m.id}`, component: ViewStub })
}
const oldMatched = oldRouter.resolve('/host/list').matched.map((r) => r.name)

// ---- 新写法：挂到 name 为 layout 的子路由 ----
const newRouter = makeRouter()
for (const m of menus) {
  newRouter.addRoute('layout', { path: m.path, name: `menu-${m.id}`, component: ViewStub })
}
newRouter.addRoute('layout', { path: '', name: 'home-redirect', redirect: '/project' })

const newMatched = newRouter.resolve('/host/list').matched.map((r) => r.name)
const homeMatched = newRouter.resolve('/').matched.map((r) => r.name)

const results = [
  ['旧写法 /host/list 命中链含布局', oldMatched.includes('layout'), false],
  ['新写法 /host/list 命中链含布局', newMatched.includes('layout'), true],
  ['新写法 / 命中链含布局', homeMatched.includes('layout'), true],
  ['新写法 /host/list 组件为菜单页', newRouter.resolve('/host/list').matched.at(-1).name, 'menu-19'],
  ['新写法 /agenthost 可达', newRouter.resolve('/agenthost').matched.at(-1).name, 'menu-24'],
]

let failed = 0
for (const [label, actual, expected] of results) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected)
  if (!ok) failed++
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${label}\n        期望=${JSON.stringify(expected)} 实际=${JSON.stringify(actual)}`)
}
console.log(`\n旧写法命中链: ${JSON.stringify(oldMatched)}`)
console.log(`新写法命中链: ${JSON.stringify(newMatched)}`)
console.log(failed ? `\n${failed} 项不通过` : '\n全部通过')
process.exit(failed ? 1 : 0)
