import { createRouter, createWebHistory } from 'vue-router'

/** 静态路由；业务菜单路由由 permission.ts 动态注册。
 * catch-all 404 不在这里静态注册——首次访问未注册的业务路由时会先被它命中，
 * 导致动态菜单路由还没来得及 addRoute 就跳到 404 页（刷新 404 的根因）。
 * catch-all 改在 permission.ts 动态路由注册完之后再挂载。 */
const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'login', component: () => import('@/views/login/index.vue'), meta: { title: '登录' } },
    {
      path: '/',
      // 必须有 name：业务菜单路由以 addRoute('layout', …) 挂到它下面，
      // 否则会被注册成顶层路由，页面脱离 DefaultLayout（表现为侧边栏消失）。
      name: 'layout',
      component: () => import('@/layouts/DefaultLayout.vue'),
      children: [],
    },
    { path: '/403', name: '403', component: () => import('@/views/error/403.vue'), meta: { title: '无权限' } },
  ],
})

export default router
