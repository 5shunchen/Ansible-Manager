/** axios 封装：统一解包 {code,message,data}、401 跳登录。 */
import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { useAuthStore } from '@/stores/auth'
import { AGENT_HOST_STORAGE_KEY } from '@/utils/scope'

export interface ApiResp<T = any> {
  code: number
  message: string
  data: T
}

export interface PageData<T = any> {
  items: T[]
  total: number
  page: number
  page_size: number
}

const request = axios.create({ baseURL: '/api/v1', timeout: 30000 })

request.interceptors.request.use((config) => {
  const auth = useAuthStore()
  if (auth.token) config.headers.Authorization = `Bearer ${auth.token}`
  // 全局作用域：所有请求带上当前 Agent 主机，后端据此收窄数据
  const scope = localStorage.getItem(AGENT_HOST_STORAGE_KEY)
  if (scope) config.headers['X-Agent-Host-Id'] = scope
  return config
})

request.interceptors.response.use(
  (resp) => {
    // 文件下载（blob）不参与 {code,message,data} 解包
    if (resp.config.responseType === 'blob') return resp
    const body = resp.data as ApiResp
    if (body.code === 0) return body
    ElMessage.error(body.message || '请求失败')
    return Promise.reject(new Error(body.message))
  },
  (err) => {
    const status = err.response?.status
    const body = err.response?.data
    if (status === 401) {
      const auth = useAuthStore()
      auth.logout()
      router.push('/login')
    }
    ElMessage.error(body?.message || err.message || '网络错误')
    return Promise.reject(err)
  },
)

export default request
