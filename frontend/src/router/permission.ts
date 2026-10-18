import type { App } from 'vue'
import type { Router } from 'vue-router'
import request from '@/api/request'
import { useAuthStore } from '@/stores/auth'
import { useMenuStore } from '@/stores/menu'

/** views 组件懒加载映射：菜单 component 字段 → 文件 */
const viewModules = import.meta.glob('../views/**/*.vue')

function resolveComponent(component: string) {
  const key = `../views/${component}.vue`
  return viewModules[key]
}

/** 已注册路由所对应的 token：退出登录后 token 变化，需重新拉菜单并注册 */
let registeredToken = ''

export default function setupPermission(app: App) {
  const router = app.config.globalProperties.$router as Router

  router.beforeEach(async (to, _from, next) => {
    const auth = useAuthStore()
    if (to.path === '/login') return next()
    if (!auth.token) return next('/login')

    if (auth.token !== registeredToken) {
      try {
        const resp = await request.get('/auth/me')
        const { menus, permissions, latest_agent_version } = resp.data as any
        auth.setMe(menus, permissions, latest_agent_version)
        const menuStore = useMenuStore()
        menuStore.setMenus(menus)
        registerRoutes(menus)
        registeredToken = auth.token
        return next({ ...to, replace: true })
      } catch {
        auth.logout()
        return next('/login')
      }
    }
    next()
  })

  /** 已动态注册的子路由名：重新登录 / 换用户时先移除，避免残留上一个用户的菜单 */
  let registeredNames: string[] = []

  function registerRoutes(menus: any[]) {
    // 平铺（含 dir 子菜单）
    const flat: any[] = []
    const walk = (nodes: any[]) => {
      for (const m of nodes) {
        if (m.menu_type === 'button') continue
        if (m.path && m.component && resolveComponent(m.component)) {
          flat.push(m)
        }
        if (m.children?.length) walk(m.children)
      }
    }
    walk(menus)

    for (const name of registeredNames) {
      if (router.hasRoute(name)) router.removeRoute(name)
    }
    registeredNames = []

    // 必须挂到 layout 子路由（name: 'layout'）下。菜单路径以 '/' 开头属于绝对路径，
    // vue-router 会原样注册，因此页面依旧由 DefaultLayout 承载，侧边栏不会消失。
    for (const m of flat) {
      const name = `menu-${m.id}`
      router.addRoute('layout', {
        path: m.path,
        name,
        component: resolveComponent(m.component) as any,
        meta: { title: m.name },
      })
      registeredNames.push(name)
    }

    // 首页重定向到第一个菜单：作为 layout 的空路径子路由（即 '/'），
    // 不再重复注册顶层 '/'，否则会与布局路由冲突导致首页空白。
    const first = flat[0]
    if (first) {
      router.addRoute('layout', {
        path: '',
        name: 'home-redirect',
        redirect: first.path,
      })
      registeredNames.push('home-redirect')
    }

    // catch-all 404 在动态路由注册完之后才挂载：避免刷新时未注册业务路由被先命中。
    if (!router.hasRoute('catch-all')) {
      router.addRoute({
        path: '/:pathMatch(.*)*',
        name: 'catch-all',
        component: () => import('@/views/error/404.vue'),
        meta: { title: '404' },
      })
    }
  }
}
