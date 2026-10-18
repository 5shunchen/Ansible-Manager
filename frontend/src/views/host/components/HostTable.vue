<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span class="card-title">{{ title }}</span>
        <div class="header-actions">
          <el-input
            v-model="keyword"
            placeholder="主机名 / IP 搜索"
            clearable
            style="width: 220px"
            @keyup.enter="onSearch"
            @clear="onSearch"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <el-button :icon="Document" @click="onDownloadTemplate">导入模板</el-button>
          <el-upload
            class="import-upload"
            :show-file-list="false"
            :auto-upload="false"
            accept=".xlsx"
            :on-change="onImportFile"
          >
            <el-button v-permission="'host:create'" :icon="Upload" :loading="importing">导入</el-button>
          </el-upload>
          <el-button :icon="Download" @click="onExport">导出</el-button>
          <el-button
            v-permission="'host:check'"
            type="warning"
            :loading="checking"
            :disabled="!selected.length"
            @click="onCheck"
          >
            连通检测
          </el-button>
          <el-button
            :icon="Monitor"
            :disabled="!selected.length"
            :loading="batchTermLoading"
            @click="onBatchTerminal"
          >
            批量终端
          </el-button>
          <el-button
            :icon="Key"
            :disabled="!selected.length"
            :loading="batchFreeLoading"
            @click="onBatchFreePassword"
          >
            批量免密
          </el-button>
          <el-button v-permission="'host:create'" type="primary" :icon="Plus" @click="openCreate">
            新增主机
          </el-button>
        </div>
      </div>
    </template>

    <el-table :data="list" v-loading="loading" row-key="id" @selection-change="onSelectionChange">
      <el-table-column type="selection" width="44" />
      <el-table-column prop="hostname" label="主机名" min-width="130" show-overflow-tooltip />
      <el-table-column prop="ip" label="IP" width="130" show-overflow-tooltip />
      <el-table-column prop="port" label="端口" width="70" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row.status)">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="!hostType" label="类型" width="90">
        <template #default="{ row }">
          <el-tag :type="typeTagType(row.host_type)" effect="plain">{{ typeText(row.host_type) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="hostType === 'agent'" label="Agent 状态" width="110">
        <template #default="{ row }">
          <el-tag :type="agentStatusTag(row.agent_status)" effect="dark">
            {{ agentStatusText(row.agent_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="hostType === 'agent'" label="Agent 版本" width="100">
        <template #default="{ row }">
          <span v-if="row.agent_version" class="agent-version">v{{ row.agent_version }}</span>
          <span v-else class="text-muted">-</span>
        </template>
      </el-table-column>
      <el-table-column v-if="hostType === 'agent'" label="Playbook 目录" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ row.playbook_dir || '-' }}</template>
      </el-table-column>
      <el-table-column v-if="hostType === 'app'" label="App 版本" width="160">
        <template #default="{ row }">
          <template v-if="appVersionOf(row)">
            <el-tag
              size="small"
              :type="appVersionOf(row).upToDate ? 'success' : 'warning'"
 effect="plain"
            >{{ appVersionOf(row).version || '-' }}</el-tag>
            <el-tag v-if="!appVersionOf(row).upToDate" size="small" type="info" effect="plain" style="margin-left:4px">有更新</el-tag>
          </template>
          <span v-else class="text-muted">未部署</span>
        </template>
      </el-table-column>
      <el-table-column label="系统" width="100" show-overflow-tooltip>
        <template #default="{ row }">{{ row.os_type || '-' }}</template>
      </el-table-column>
      <el-table-column label="CPU(核)" width="90">
        <template #default="{ row }">{{ row.cpu_cores ?? '-' }}</template>
      </el-table-column>
      <el-table-column label="内存" width="100">
        <template #default="{ row }">{{ fmtMem(row.mem_total_mb) }}</template>
      </el-table-column>
      <el-table-column v-if="!hostType" label="所属项目" min-width="110" show-overflow-tooltip>
        <template #default="{ row }">{{ projectName(row.project_id) }}</template>
      </el-table-column>
      <el-table-column label="采集时间" width="165">
        <template #default="{ row }">{{ fmtTime(row.last_collect_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="430" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" title="连接测试" @click="onRowCheck(row)">
            <el-icon><CircleCheck /></el-icon>
          </el-button>
          <el-button link type="success" title="Web 终端" @click="onRowTerminal(row)">
            <el-icon><Monitor /></el-icon>
          </el-button>
          <el-button link type="warning" title="文件管理" @click="onRowFiles(row)">
            <el-icon><FolderOpened /></el-icon>
          </el-button>
          <el-button link type="info" title="SSH 免密" :loading="freeRow[`row-${row.id}`]" @click="onRowFreePassword(row)">
            <el-icon><Key /></el-icon>
          </el-button>
          <template v-if="hostType === 'agent'">
            <el-button
              v-if="row.agent_status !== 'installed' && row.agent_status !== 'running'"
              link type="success" title="安装 Agent"
              :loading="agentRow[`install-${row.id}`]"
              @click="onAgentAction('install', row)"
            >安装</el-button>
            <el-button
              v-if="canUpdate(row)"
              link type="primary" title="更新 Agent"
              :loading="agentRow[`update-${row.id}`]"
              @click="onAgentAction('update', row)"
            >更新</el-button>
            <el-button
              v-if="row.agent_status === 'installed' || row.agent_status === 'running'"
              link type="danger" title="卸载 Agent"
              :loading="agentRow[`uninstall-${row.id}`]"
              @click="onAgentAction('uninstall', row)"
            >卸载</el-button>
          </template>
          <template v-if="hostType === 'app'">
            <el-button
              v-if="!appVersionOf(row) || appVersionOf(row).status === 'uninstalled'"
              v-permission="'app:install'"
              link type="primary" title="部署 App"
              @click="openInstallApp(row)"
            >部署</el-button>
            <el-button
              v-else-if="!appVersionOf(row).upToDate"
              v-permission="'app:install'"
              link type="warning" title="镜像有新版本，点击更新"
              :loading="appActionRow[`update-${row.id}`]"
              @click="onUpdateApp(row)"
            >更新</el-button>
            <el-button
              v-if="appVersionOf(row) && appVersionOf(row).status !== 'uninstalled'"
              v-permission="'app:uninstall'"
              link type="danger" title="卸载 App"
              :loading="appActionRow[`uninstall-${row.id}`]"
              @click="onUninstallApp(row)"
            >卸载</el-button>
            <el-button link type="info" title="已安装的 App" @click="openAppDrawer(row)">详情</el-button>
          </template>
          <el-button v-permission="'host:update'" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-permission="'host:delete'" link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        background
        layout="total, sizes, prev, pager, next, jumper"
        :page-sizes="[10, 20, 50, 100]"
        :total="total"
        @current-change="load"
        @size-change="onSizeChange"
      />
    </div>

    <el-dialog v-model="dialog.visible" :title="dialog.isEdit ? '编辑主机' : '新增主机'" width="520px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="主机名" prop="hostname">
          <el-input v-model="form.hostname" placeholder="如：web-01" maxlength="128" />
        </el-form-item>
        <el-form-item label="IP 地址" prop="ip">
          <el-input v-model="form.ip" placeholder="如：10.0.0.11" maxlength="64" />
        </el-form-item>
        <el-form-item label="SSH 端口" prop="port">
          <el-input-number v-model="form.port" :min="1" :max="65535" controls-position="right" style="width: 160px" />
        </el-form-item>
        <el-form-item v-if="!hostType" label="主机类型" prop="host_type">
          <el-select v-model="form.host_type" style="width: 100%">
            <el-option label="应用主机" value="app" />
            <el-option label="Agent 主机" value="agent" />
            <el-option label="普通主机" value="managed" />
          </el-select>
        </el-form-item>
        <!-- Agent 主机专属：Playbook 存放目录（hostType=agent 时固定显示） -->
        <el-form-item v-if="hostType === 'agent' || form.host_type === 'agent'" label="Playbook 目录">
          <el-input v-model="form.playbook_dir" placeholder="/opt/ansible" maxlength="255" />
          <div class="form-tip">该 Agent 主机的 playbook 文件存放位置，默认 /opt/ansible</div>
        </el-form-item>
        <el-form-item label="登录用户" prop="ssh_username">
          <el-input v-model="form.ssh_username" placeholder="默认 root" maxlength="64" />
        </el-form-item>
        <el-form-item label="主机密码" prop="ssh_password">
          <div class="pwd-row">
            <el-input
              v-model="form.ssh_password"
              type="password"
              show-password
              :placeholder="dialog.isEdit ? '留空表示不修改密码' : '输入主机 SSH 密码'"
              style="flex: 1"
            />
            <el-button :loading="testing" @click="onTestConn">连接测试</el-button>
          </div>
        </el-form-item>

        <!-- 连接测试结果 -->
        <el-form-item v-if="connResult">
          <el-alert
            :title="connResult.title"
            :type="connResult.ok ? 'success' : 'error'"
            :description="connResult.desc"
            :closable="false"
            style="width: 100%"
          />
        </el-form-item>

        <el-form-item label="所属项目" prop="project_id">
          <el-select v-model="form.project_id" clearable placeholder="不归属任何项目" style="width: 100%">
            <el-option v-for="p in projects" :key="p.id" :value="p.id" :label="p.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="主机描述（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取 消</el-button>
        <el-button type="primary" :loading="dialog.saving" @click="onSave">确 定</el-button>
      </template>
    </el-dialog>

    <!-- 导入结果：保留每行失败原因，便于按行修正后重导 -->
    <el-dialog v-model="importDialog" title="导入结果" width="680px">
      <el-alert
        :type="importResult.failed ? 'warning' : 'success'"
        :closable="false"
        show-icon
        :title="`共 ${importResult.total} 行，成功 ${importResult.success} 行，失败 ${importResult.failed} 行`"
      />
      <el-table
        v-if="importResult.errors?.length"
        :data="importResult.errors"
        size="small"
        max-height="320"
        class="import-errors"
      >
        <el-table-column prop="line" label="行号" width="70" />
        <el-table-column prop="hostname" label="主机名" width="160" />
        <el-table-column prop="message" label="失败原因" />
      </el-table>
      <template #footer>
        <el-button type="primary" @click="importDialog = false">知道了</el-button>
      </template>
    </el-dialog>

    <InstallAppDialog v-model="installAppVisible" :host="installAppHost" @installed="onAppInstalled" />
    <HostAppDrawer v-model="appDrawerVisible" :host="appDrawerHost" />
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Search, Plus, Document, Download, Upload, CircleCheck, Monitor, FolderOpened, Key } from '@element-plus/icons-vue'
import request from '@/api/request'
import { useAuthStore } from '@/stores/auth'
import {
  listHosts, createHost, updateHost, deleteHost, checkHost,
  listCredentials, listProjects,
  exportHostsCsv, importHostsCsv, downloadHostImportTemplate,
} from '@/api/modules'
import InstallAppDialog from './InstallAppDialog.vue'
import HostAppDrawer from './HostAppDrawer.vue'
import { listHostApps, installApp, uninstallApp, listInstalledPlugins } from '@/api/modules'

const auth = useAuthStore()
const props = defineProps<{ hostType: string; title: string }>()

const loading = ref(false)
const checking = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const keyword = ref('')
const selected = ref<any[]>([])

const credentials = ref<any[]>([])
const projects = ref<any[]>([])

const importing = ref(false)
const importDialog = ref(false)
const importResult = ref<any>({ total: 0, success: 0, failed: 0, errors: [] })

const formRef = ref<FormInstance>()
const dialog = reactive({ visible: false, isEdit: false, saving: false, id: 0 })
const form = reactive({
  hostname: '',
  ip: '',
  port: 22,
  host_type: 'managed',
  ssh_username: 'root',
  ssh_password: '',
  credential_id: undefined as number | undefined,
  project_id: undefined as number | undefined,
  description: '',
  playbook_dir: '/opt/ansible',
})

const testing = ref(false)
const connResult = ref<{ ok: boolean; title: string; desc: string } | null>(null)

const rules: FormRules = {
  hostname: [{ required: true, message: '请输入主机名', trigger: 'blur' }],
  ip: [{ required: true, message: '请输入 IP 地址', trigger: 'blur' }],
  port: [{ required: true, message: '请输入 SSH 端口', trigger: 'blur' }],
  host_type: [{ required: true, message: '请选择主机类型', trigger: 'change' }],
  ssh_password: [{ required: true, message: '请输入主机密码', trigger: 'blur' }],
}

// ---------- 展示辅助 ----------
function statusTagType(s: string): 'success' | 'danger' | 'info' {
  if (s === 'online') return 'success'
  if (s === 'offline') return 'danger'
  return 'info'
}
function statusText(s: string) {
  if (s === 'online') return '在线'
  if (s === 'offline') return '离线'
  if (s === 'unknown') return '未知'
  return s || '-'
}
function typeText(t: string) {
  if (t === 'app') return '应用'
  if (t === 'agent') return 'Agent'
  return '普通'
}
function typeTagType(t: string): 'primary' | 'warning' | 'info' {
  if (t === 'app') return 'primary'
  if (t === 'agent') return 'warning'
  return 'info'
}
function agentStatusText(s: string) {
  if (s === 'running') return '运行中'
  if (s === 'installed') return '已安装'
  if (s === 'error') return '异常'
  return '未安装'
}
function agentStatusTag(s: string): 'success' | 'primary' | 'danger' | 'info' {
  if (s === 'running') return 'success'
  if (s === 'installed') return 'primary'
  if (s === 'error') return 'danger'
  return 'info'
}

/** 语义化版本比较：v1 > v2 */
function gtVersion(v1: string, v2: string): boolean {
  const a = String(v1 || '').split('.').map((x) => parseInt(x, 10) || 0)
  const b = String(v2 || '').split('.').map((x) => parseInt(x, 10) || 0)
  for (let i = 0; i < Math.max(a.length, b.length); i++) {
    if ((a[i] || 0) !== (b[i] || 0)) return (a[i] || 0) > (b[i] || 0)
  }
  return false
}

/** 更新按钮显示条件：已安装 且 系统最新版 > 数据库已装版 */
function canUpdate(row: any): boolean {
  const st = row.agent_status
  if (st !== 'installed' && st !== 'running') return false
  const latest = auth.latestAgentVersion
  if (!latest) return false
  return gtVersion(latest, row.agent_version || '')
}

// Agent 安装/卸载/更新
const agentRow = reactive<Record<string, boolean>>({})
async function onAgentAction(action: 'install' | 'uninstall' | 'update', row: any) {
  agentRow[`${action}-${row.id}`] = true
  try {
    await request.post(`/hosts/${row.id}/agent/${action}`)
    const label = { install: '安装', uninstall: '卸载', update: '更新' }[action]
    ElMessage.success(`${row.hostname} Agent${label}成功`)
    load()
  } catch {
    /* 拦截器已提示 */
  } finally {
    agentRow[`${action}-${row.id}`] = false
  }
}
function fmtMem(mb: any) {
  if (!mb) return '-'
  return Number(mb) >= 1024 ? `${(Number(mb) / 1024).toFixed(1)} GB` : `${mb} MB`
}
function fmtTime(t: any) {
  if (!t) return '-'
  return String(t).replace('T', ' ').slice(0, 19)
}
function projectName(id: any) {
  if (!id) return '-'
  return projects.value.find((p) => p.id === id)?.name || '-'
}

// ---------- 数据加载 ----------
async function load() {
  loading.value = true
  try {
    const params: any = { page: page.value, page_size: pageSize.value }
    if (keyword.value.trim()) params.keyword = keyword.value.trim()
    if (props.hostType) params.host_type = props.hostType
    const resp = await listHosts(params)
    const data = resp.data as any
    list.value = data?.items || []
    total.value = data?.total || 0
    // 应用主机页：并行拉每台主机已装 app + 最新插件版本
    if (props.hostType === 'app') {
      Promise.all([loadHostApps(), loadLatestVersion()]).catch(() => {})
    }
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  try {
    const [credResp, projResp] = await Promise.all([listCredentials(), listProjects()])
    credentials.value = (credResp.data as any[]) || []
    projects.value = (projResp.data as any[]) || []
  } catch {
    /* 拦截器已提示 */
  }
}

function onSearch() {
  page.value = 1
  load()
}

function onSizeChange() {
  // 页码归 1；若页码变化会由 current-change 触发 load，否则手动加载
  if (page.value !== 1) {
    page.value = 1
  } else {
    load()
  }
}

function onSelectionChange(rows: any[]) {
  selected.value = rows
}

// ---------- 新增 / 编辑 ----------
function openCreate() {
  dialog.isEdit = false
  dialog.id = 0
  form.hostname = ''
  form.ip = ''
  form.port = 22
  form.host_type = props.hostType || 'managed'
  form.ssh_username = 'root'
  form.ssh_password = ''
  form.credential_id = undefined
  form.project_id = undefined
  form.description = ''
  connResult.value = null
  dialog.visible = true
}

function openEdit(row: any) {
  dialog.isEdit = true
  dialog.id = row.id
  form.hostname = row.hostname
  form.ip = row.ip
  form.port = row.port || 22
  form.host_type = row.host_type || props.hostType || 'managed'
  form.ssh_username = 'root'
  form.ssh_password = ''
  form.credential_id = row.credential_id
  form.project_id = row.project_id ?? undefined
  form.description = row.description || ''
  connResult.value = null
  dialog.visible = true
}

// 连接测试（建表单内即时验证，不入库）
async function onTestConn() {
  if (!form.ip || !form.ssh_password) return ElMessage.warning('请先填写 IP 和主机密码')
  testing.value = true
  connResult.value = null
  try {
    const resp = await request.post('/hosts/check-connect', null, {
      params: {
        ip: form.ip, port: Number(form.port) || 22,
        username: form.ssh_username || 'root', password: form.ssh_password,
      },
    })
    const d = resp.data as any
    connResult.value = {
      ok: true,
      title: '连接成功',
      desc: `${d.os || 'Linux'} ${d.os_release || ''} · ${d.cpu_cores ?? '?'} 核`,
    }
  } catch (e: any) {
    connResult.value = { ok: false, title: '连接失败', desc: e?.response?.data?.message || '请检查 IP、端口、用户名或密码' }
  } finally {
    testing.value = false
  }
}

async function onSave() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  // 编辑时密码可留空（不改）
  if (!dialog.isEdit && !form.ssh_password) return ElMessage.warning('请输入主机密码')
  dialog.saving = true
  try {
    const payload: any = {
      hostname: form.hostname,
      ip: form.ip,
      port: form.port,
      host_type: form.host_type,
      ssh_username: form.ssh_username || 'root',
      project_id: form.project_id || null,
      description: form.description,
    }
    // Agent 主机带上 playbook 存放目录
    const isAgent = props.hostType === 'agent' || form.host_type === 'agent'
    if (isAgent && form.playbook_dir) {
      payload.playbook_dir = form.playbook_dir
      payload.host_type = 'agent'
    }
    if (form.ssh_password) payload.ssh_password = form.ssh_password
    if (dialog.isEdit) {
      await updateHost(dialog.id, payload)
      ElMessage.success('修改成功')
    } else {
      await createHost(payload)
      ElMessage.success('新增成功')
    }
    dialog.visible = false
    load()
  } catch {
    /* 拦截器已提示 */
  } finally {
    dialog.saving = false
  }
}

// ---------- 删除 / 连通检测 ----------
async function onDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除主机「${row.hostname}（${row.ip}）」？删除后不可恢复。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteHost(row.id)
    ElMessage.success('已删除')
    if (list.value.length === 1 && page.value > 1) page.value -= 1
    load()
  } catch {
    /* 拦截器已提示 */
  }
}

async function onCheck() {
  if (!selected.value.length) return ElMessage.warning('请先勾选需要检测的主机')
  checking.value = true
  try {
    for (const h of selected.value) {
      try {
        const resp = await checkHost(h.id)
        const r = resp.data as any
        if (r?.reachable) {
          const info = [r.os_type, r.os_release].filter(Boolean).join(' ')
          ElMessage.success(`${h.hostname} 连通正常${info ? `（${info}）` : ''}`)
        } else {
          ElMessage.error(`${h.hostname} 连通失败：${r?.message || '未知原因'}`)
        }
      } catch {
        /* 拦截器已提示，继续检测下一台 */
      }
    }
    load()
  } finally {
    checking.value = false
  }
}

// ---------- 行操作：连接测试 / 终端 / 文件 / 免密 ----------
async function onRowCheck(row: any) {
  try {
    const resp = await checkHost(row.id)
    const r = resp.data as any
    if (r?.reachable) {
      const info = [r.os_type, r.os_release].filter(Boolean).join(' ')
      ElMessage.success(`${row.hostname} 连通正常${info ? `（${info}）` : ''}`)
    } else {
      ElMessage.error(`${row.hostname} 连通失败：${r?.message || '未知原因'}`)
    }
  } catch {
    /* 拦截器已提示 */
  }
}

function onRowTerminal(row: any) {
  // 跳转终端页（同页多标签，每个主机一个独立标签）
  window.location.href = `/host/terminal?host_id=${row.id}`
}

function onRowFiles(row: any) {
  // 跳转文件管理页（同页多标签，每个主机一个独立标签）
  window.location.href = `/host/files?host_id=${row.id}`
}

const freeRow = reactive<Record<string, boolean>>({})
async function onRowFreePassword(row: any) {
  freeRow[`row-${row.id}`] = true
  try {
    await request.post(`/hosts/${row.id}/passwordless`)
    ElMessage.success(`${row.hostname} 免密登录已配置`)
  } catch {
    /* 拦截器已提示 */
  } finally {
    freeRow[`row-${row.id}`] = false
  }
}

// ---------- 批量操作 ----------
const batchTermLoading = ref(false)
function onBatchTerminal() {
  if (!selected.value.length) return ElMessage.warning('请先勾选主机')
  // 跳转终端页并预选第一台（终端页支持后续多标签）
  const first = selected.value[0]
  window.location.href = `/host/terminal?host_id=${first.id}`
  ElMessage.success(`已进入终端页，可在页面内为每台主机打开标签`)
}

const batchFreeLoading = ref(false)
async function onBatchFreePassword() {
  if (!selected.value.length) return ElMessage.warning('请先勾选主机')
  batchFreeLoading.value = true
  let ok = 0
  try {
    for (const h of selected.value) {
      try {
        await request.post(`/hosts/${h.id}/passwordless`)
        ok++
      } catch {
        /* 拦截器已提示，继续下一台 */
      }
    }
    ElMessage.success(`批量免密完成：成功 ${ok}/${selected.value.length} 台`)
  } finally {
    batchFreeLoading.value = false
  }
}

// ---------- 导入导出 ----------
function saveBlob(data: Blob, filename: string) {
  const url = URL.createObjectURL(data)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

async function onDownloadTemplate() {
  const resp = await downloadHostImportTemplate()
  saveBlob(resp.data as Blob, 'host-import-template.xlsx')
}

async function onExport() {
  const params: any = {}
  if (props.hostType) params.host_type = props.hostType
  const resp = await exportHostsCsv(params)
  saveBlob(resp.data as Blob, `hosts-${Date.now()}.xlsx`)
}

async function onImportFile(uploadFile: any) {
  const file = uploadFile?.raw
  if (!file) return
  importing.value = true
  try {
    const resp = await importHostsCsv(file)
    importResult.value = resp.data
    importDialog.value = true
    if (!importResult.value.failed) {
      ElMessage.success(`导入完成：成功 ${importResult.value.success} 条`)
    }
    page.value = 1
    await load()
  } finally {
    importing.value = false
  }
}

// ---------- App 安装（仅应用主机）----------
const router = useRouter()
const installAppVisible = ref(false)
const installAppHost = ref<any>(null)
const appDrawerVisible = ref(false)
const appDrawerHost = ref<any>(null)

// 每台应用主机当前装的 app（含版本/状态），用于行内按钮与版本列
const hostAppsMap = ref<Record<number, any>>({})
// 控制端"最新"插件版本（plugin.version，build 后由 refresh-image 写回）
const latestAppVersion = ref<string>('')
const appActionRow = reactive<Record<string, boolean>>({})

function appVersionOf(row: any) {
  const ha = hostAppsMap.value[row.id]
  if (!ha) return null
  return {
    version: ha.version,
    status: ha.status,
    upToDate: !latestAppVersion.value || ha.version === latestAppVersion.value,
  }
}

async function loadHostApps() {
  if (props.hostType !== 'app') return
  // 拉所有应用主机的 app 记录：后端没有批量接口，逐台拉代价大；改成只拉当前页
  const map: Record<number, any> = {}
  for (const h of list.value) {
    try {
      const resp = await listHostApps(h.id)
      const rows = (resp.data as any[]) || []
      // 只取最近一条已安装/安装中的
      const rec = rows.find((r) => r.status === 'installed' || r.status === 'installing' || r.status === 'uninstalling')
        || rows[0]
      if (rec) map[h.id] = rec
    } catch { /* ignore */ }
  }
  hostAppsMap.value = map
}

async function loadLatestVersion() {
  if (props.hostType !== 'app') return
  try {
    const resp = await listInstalledPlugins()
    const plugins = (resp.data as any[]) || []
    const amApp = plugins.find((p) => p.name === 'am-app') || plugins[0]
    if (amApp) latestAppVersion.value = amApp.version || ''
  } catch { /* ignore */ }
}

function openInstallApp(row: any) {
  installAppHost.value = row
  installAppVisible.value = true
}
function openAppDrawer(row: any) {
  appDrawerHost.value = row
  appDrawerVisible.value = true
}
function onAppInstalled(_taskId: number) {
  router.push('/task')
}

async function onUpdateApp(row: any) {
  // 更新 = 重新部署（后端幂等：重新 import 新镜像 → 停旧容器 → 起新容器）
  const ha = hostAppsMap.value[row.id]
  appActionRow[`update-${row.id}`] = true
  try {
    await installApp({ host_id: row.id, plugin_id: ha.plugin_id })
    ElMessage.success('已触发更新，可到任务管理页查看进度')
    router.push('/task')
  } catch { /* 拦截器已提示 */ } finally {
    appActionRow[`update-${row.id}`] = false
  }
}

async function onUninstallApp(row: any) {
  const ha = hostAppsMap.value[row.id]
  try {
    await ElMessageBox.confirm(`确认卸载 ${row.hostname} 上的 ${ha?.plugin_name || 'App'}？将在后台拉起卸载任务。`, '卸载确认', {
      type: 'warning', confirmButtonText: '卸载', cancelButtonText: '取消',
    })
  } catch { return }
  appActionRow[`uninstall-${row.id}`] = true
  try {
    await uninstallApp({ host_id: row.id, plugin_id: ha.plugin_id })
    ElMessage.success('卸载任务已提交，可到任务管理页查看进度')
    router.push('/task')
  } catch { /* 拦截器已提示 */ } finally {
    appActionRow[`uninstall-${row.id}`] = false
  }
}

onMounted(() => {
  load()
  loadOptions()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card-title {
  font-size: 16px;
  font-weight: 600;
}
.form-tip {
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
  margin-top: 4px;
}
.header-actions :deep(.el-upload) {
  display: inline-block;
}
.import-errors {
  margin-top: 12px;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 4px;
}
.pager {
  margin-top: 14px;
  display: flex;
  justify-content: flex-end;
}
.pwd-row { display: flex; gap: 8px; width: 100%; align-items: center; }
.agent-version { font-family: 'JetBrains Mono', Consolas, monospace; font-size: 12px; color: #303133; }
.text-muted { color: #c0c4cc; }
</style>
