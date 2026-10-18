import { defineStore } from 'pinia'

export interface UserInfo {
  id: number
  username: string
  nickname: string
  is_superuser: boolean
  roles: string[]
}

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: (localStorage.getItem('token') as string) || '',
    user: JSON.parse(localStorage.getItem('user') || 'null') as UserInfo | null,
    permissions: [] as string[],
    menus: [] as any[],
    latestAgentVersion: '',
  }),
  getters: {
    isLoggedIn: (s) => !!s.token,
  },
  actions: {
    setAuth(token: string, user: UserInfo) {
      this.token = token
      this.user = user
      localStorage.setItem('token', token)
      localStorage.setItem('user', JSON.stringify(user))
    },
    setMe(menus: any[], permissions: string[], latestAgentVersion = '') {
      this.menus = menus
      this.permissions = permissions
      this.latestAgentVersion = latestAgentVersion
    },
    logout() {
      this.token = ''
      this.user = null
      this.menus = []
      this.permissions = []
      this.latestAgentVersion = ''
      localStorage.removeItem('token')
      localStorage.removeItem('user')
    },
  },
})
