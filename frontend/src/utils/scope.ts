/**
 * Agent 主机作用域的本地持久化读写。
 *
 * 单独抽出来是为了让 axios 请求拦截器不依赖 pinia store，
 * 避免 store → api → request → store 的循环导入。
 */
export const AGENT_HOST_STORAGE_KEY = 'current_agent_host_id'

export function getStoredAgentHostId(): number | undefined {
  const raw = localStorage.getItem(AGENT_HOST_STORAGE_KEY)
  const id = Number(raw)
  return raw && Number.isFinite(id) && id > 0 ? id : undefined
}

export function setStoredAgentHostId(id?: number): void {
  if (id) localStorage.setItem(AGENT_HOST_STORAGE_KEY, String(id))
  else localStorage.removeItem(AGENT_HOST_STORAGE_KEY)
}
