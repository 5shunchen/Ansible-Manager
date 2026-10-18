/** 各域 API 模块汇总。 */
import request from './request'

// ---- auth ----
export const login = (data: { username: string; password: string }) => request.post('/auth/login', data)
export const fetchMe = () => request.get('/auth/me')

// ---- projects ----
export const listProjects = () => request.get('/projects')
export const createProject = (data: any) => request.post('/projects', data)
export const updateProject = (id: number, data: any) => request.put(`/projects/${id}`, data)
export const deleteProject = (id: number) => request.delete(`/projects/${id}`)

// ---- credentials ----
export const listCredentials = () => request.get('/credentials')
export const createCredential = (data: any) => request.post('/credentials', data)
export const updateCredential = (id: number, data: any) => request.put(`/credentials/${id}`, data)
export const deleteCredential = (id: number) => request.delete(`/credentials/${id}`)

// ---- host groups ----
export const listGroups = () => request.get('/host-groups')
export const createGroup = (data: any) => request.post('/host-groups', data)
export const updateGroup = (id: number, data: any) => request.put(`/host-groups/${id}`, data)
export const deleteGroup = (id: number) => request.delete(`/host-groups/${id}`)

// ---- hosts ----
export const listHosts = (params: any) => request.get('/hosts', { params })
export const createHost = (data: any) => request.post('/hosts', data)
export const updateHost = (id: number, data: any) => request.put(`/hosts/${id}`, data)
export const deleteHost = (id: number) => request.delete(`/hosts/${id}`)
export const checkHost = (id: number) => request.post(`/hosts/${id}/check`)

// ---- hosts 导入导出（blob 下载绕开统一解包）----
export const exportHostsCsv = (params: any) =>
  request.get('/hosts/export', { params, responseType: 'blob' })
export const downloadHostImportTemplate = () =>
  request.get('/hosts/import-template', { responseType: 'blob' })
export const importHostsCsv = (file: File) => {
  const fd = new FormData()
  fd.append('file', file)
  return request.post('/hosts/import', fd)
}

// ---- files (SFTP) ----
export const listHostFiles = (hostId: number, path: string) => request.get(`/hosts/${hostId}/files`, { params: { path } })
export const uploadHostFile = (hostId: number, path: string, file: File) => {
  const fd = new FormData()
  fd.append('file', file)
  return request.post(`/hosts/${hostId}/files/upload`, fd, { params: { path } })
}
export const downloadHostFileUrl = (hostId: number, path: string, token: string) =>
  `/api/v1/hosts/${hostId}/files/download?path=${encodeURIComponent(path)}&token=${token}`
export const mkdirHostFile = (hostId: number, path: string, name: string) => request.post(`/hosts/${hostId}/files/mkdir`, null, { params: { path, name } })
export const renameHostFile = (hostId: number, path: string, newPath: string) => request.post(`/hosts/${hostId}/files/rename`, null, { params: { path, new_path: newPath } })
export const deleteHostFile = (hostId: number, path: string) => request.delete(`/hosts/${hostId}/files`, { params: { path } })

// ---- playbooks ----
export const listPlaybooks = (keyword?: string) => request.get('/playbooks', { params: { keyword } })
export const createPlaybook = (data: any) => request.post('/playbooks', data)
export const updatePlaybook = (id: number, data: any) => request.put(`/playbooks/${id}`, data)
export const deletePlaybook = (id: number) => request.delete(`/playbooks/${id}`)
export const listPlaybookFiles = (id: number) => request.get(`/playbooks/${id}/files`)
export const readPlaybookFile = (id: number, path: string) => request.get(`/playbooks/${id}/files/content`, { params: { path } })
export const writePlaybookFile = (id: number, path: string, content: string) => request.put(`/playbooks/${id}/files/content`, { path, content })
export const validatePlaybook = (id: number, path?: string) => request.post(`/playbooks/${id}/validate`, null, { params: { path } })

// ---- tasks ----
export const listTasks = (params: any) => request.get('/tasks', { params })
export const createTask = (data: any) => request.post('/tasks', data)
export const getTask = (id: number) => request.get(`/tasks/${id}`)
export const listTaskEvents = (id: number, afterSeq = 0) => request.get(`/tasks/${id}/events`, { params: { after_seq: afterSeq } })
export const cancelTask = (id: number) => request.post(`/tasks/${id}/cancel`)
export const deleteTask = (id: number) => request.delete(`/tasks/${id}`)

// ---- metrics ----
export const hostMetricHistory = (hostId: number, params: any) => request.get(`/metrics/hosts/${hostId}/history`, { params })
export const hostCurrentMetric = (hostId: number) => request.get(`/metrics/hosts/${hostId}/current`)
export const dashboardOverview = () => request.get('/dashboard/overview')

// ---- users / roles / menus ----
export const listUsers = (params: any) => request.get('/users', { params })
export const createUser = (data: any) => request.post('/users', data)
export const updateUser = (id: number, data: any) => request.put(`/users/${id}`, data)
export const deleteUser = (id: number) => request.delete(`/users/${id}`)
export const listRoles = () => request.get('/roles')
export const createRole = (data: any) => request.post('/roles', data)
export const updateRole = (id: number, data: any) => request.put(`/roles/${id}`, data)
export const deleteRole = (id: number) => request.delete(`/roles/${id}`)
export const listMenus = () => request.get('/menus')
export const menuTree = () => request.get('/menus/tree')
export const createMenu = (data: any) => request.post('/menus', data)
export const updateMenu = (id: number, data: any) => request.put(`/menus/${id}`, data)
export const deleteMenu = (id: number) => request.delete(`/menus/${id}`)

// ---- system configs / audit ----
export const listSystemConfigs = () => request.get('/system-configs')
export const updateSystemConfigs = (configs: Record<string, any>) => request.put('/system-configs', { configs })
export const listAuditLogs = (params: any) => request.get('/audit-logs', { params })

// ---- plugins ----
export const listPlugins = (keyword?: string) => request.get('/plugins', { params: { keyword } })
export const createPlugin = (data: any) => request.post('/plugins', data)
export const updatePlugin = (id: number, data: any) => request.put(`/plugins/${id}`, data)
export const installPlugin = (id: number) => request.post(`/plugins/${id}/install`)
export const deletePlugin = (id: number) => request.delete(`/plugins/${id}`)

// ---- deployment ----
export const listDeployProjects = (keyword?: string) => request.get('/deploy-projects', { params: { keyword } })
export const getDeployProject = (id: number) => request.get(`/deploy-projects/${id}`)
export const createDeployProject = (data: any) => request.post('/deploy-projects', data)
export const updateDeployProject = (id: number, data: any) => request.put(`/deploy-projects/${id}`, data)
export const deleteDeployProject = (id: number) => request.delete(`/deploy-projects/${id}`)
export const deployProject = (id: number, action: string, data?: any) => request.post(`/deploy-projects/${id}/${action}`, data || {})
export const listDeployRecords = (params: any) => request.get('/deploy-records', { params })

// ---- apps（应用主机上的插件包安装）----
export const listInstalledPlugins = () => request.get('/plugins/installed')
export const listHostApps = (hostId: number) => request.get(`/apps/host/${hostId}`)
export const installApp = (data: { host_id: number; plugin_id: number; extra_vars?: any }) =>
  request.post('/apps/install', data)
export const uninstallApp = (data: { host_id: number; plugin_id: number }) =>
  request.post('/apps/uninstall', data)
export const refreshPluginImage = (pluginId: number) =>
  request.post(`/plugins/${pluginId}/refresh-image`)
