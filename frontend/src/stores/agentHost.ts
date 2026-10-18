import { defineStore } from 'pinia'
import { listHosts } from '@/api/modules'
import { getStoredAgentHostId, setStoredAgentHostId } from '@/utils/scope'

/**
 * 全局「当前 Agent 主机」作用域。
 *
 * Agent 主机就是 Ansible 控制机，业务数据都挂在它下面；
 * 顶部筛选框选择后，所有请求都会带上该作用域，后端据此收窄数据。
 */
export const useAgentHostStore = defineStore('agentHost', {
  state: () => ({
    hosts: [] as any[],
    loading: false,
    currentId: getStoredAgentHostId(),
  }),
  getters: {
    current: (s) => s.hosts.find((h) => h.id === s.currentId),
  },
  actions: {
    async loadHosts() {
      this.loading = true
      try {
        const resp = await listHosts({ host_type: 'agent', page: 1, page_size: 100 })
        this.hosts = (resp.data as any)?.items || []
        // 已选主机被删除或类型被改，则清空选择，避免残留失效作用域
        if (this.currentId && !this.hosts.some((h) => h.id === this.currentId)) {
          this.select(undefined)
        }
      } finally {
        this.loading = false
      }
    },
    select(id?: number) {
      this.currentId = id
      setStoredAgentHostId(id)
    },
  },
})
