import { defineStore } from 'pinia'

/** 菜单树中 host_dir 的子菜单在 addRoute 时平铺到 /host 下 */
function flattenMenus(menus: any[]): any[] {
  const out: any[] = []
  for (const m of menus) {
    out.push(m)
    if (m.children?.length) out.push(...flattenMenus(m.children))
  }
  return out
}

export const useMenuStore = defineStore('menu', {
  state: () => ({
    menuTree: [] as any[],
  }),
  actions: {
    setMenus(menus: any[]) {
      this.menuTree = menus
    },
    /** element menu 渲染用的树：visible 的 dir/menu */
    sidebarMenus() {
      const filter = (nodes: any[]): any[] =>
        nodes
          .filter((m) => m.visible !== false && m.menu_type !== 'button')
          .map((m) => ({ ...m, children: m.children ? filter(m.children) : [] }))
      return filter(this.menuTree)
    },
  },
})
