<template>
  <div class="task-page">
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <div class="filters">
            <el-select
              v-model="query.status"
              placeholder="任务状态"
              clearable
              style="width: 150px"
              @change="onFilter"
            >
              <el-option v-for="s in STATUS_OPTIONS" :key="s.value" :label="s.label" :value="s.value" />
            </el-select>
            <el-select
              v-model="query.task_type"
              placeholder="任务类型"
              clearable
              style="width: 150px"
              @change="onFilter"
            >
              <el-option v-for="t in TYPE_OPTIONS" :key="t.value" :label="t.label" :value="t.value" />
            </el-select>
            <el-button :icon="Refresh" circle title="刷新" @click="loadList" />
          </div>
          <el-button type="primary" :icon="Plus" @click="openCreate">新建任务</el-button>
        </div>
      </template>

      <el-table v-loading="loading" :data="list">
        <el-table-column prop="name" label="任务名称" min-width="170" show-overflow-tooltip />
        <el-table-column label="类型" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="typeMeta(row.task_type).type">{{ typeMeta(row.task_type).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="95" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="statusMeta(row.status).type" effect="dark">{{ statusMeta(row.status).label }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="triggered_by" label="触发人" width="110" show-overflow-tooltip />
        <el-table-column label="开始时间" width="170">
          <template #default="{ row }">{{ fmtTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column label="耗时" width="95" align="right">
          <template #default="{ row }">{{ fmtDuration(row.duration_ms) }}</template>
        </el-table-column>
        <el-table-column label="RC" width="65" align="center">
          <template #default="{ row }">{{ row.rc ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="190" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openLog(row)">日志</el-button>
            <el-button v-if="isActive(row)" link type="warning" @click="onCancel(row)">取消</el-button>
            <el-button v-if="isTerminal(row)" link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        class="pager"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @current-change="loadList"
        @size-change="onFilter"
      />
    </el-card>

    <!-- 新建任务 -->
    <el-dialog v-model="createVisible" title="新建任务" width="640px" :close-on-click-modal="false">
      <el-form :model="form" label-width="100px">
        <el-form-item label="任务名称" required>
          <el-input v-model="form.name" maxlength="128" placeholder="如：发布 v1.2.0" />
        </el-form-item>
        <el-form-item label="Playbook" required>
          <el-select v-model="form.playbook_id" filterable placeholder="选择要执行的 Playbook" style="width: 100%">
            <el-option v-for="p in playbooks" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标主机" required>
          <el-select
            v-model="form.host_ids"
            multiple
            filterable
            collapse-tags
            collapse-tags-tooltip
            placeholder="选择执行主机（可多选）"
            style="width: 100%"
          >
            <el-option v-for="h in hosts" :key="h.id" :label="`${h.hostname}（${h.ip}）`" :value="h.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="额外变量">
          <el-input
            v-model="form.extra_vars_text"
            type="textarea"
            :rows="3"
            spellcheck="false"
            placeholder='JSON 格式，如 {"env": "prod", "version": "1.2.0"}'
          />
        </el-form-item>
        <el-form-item label="超时（秒）">
          <el-input-number v-model="form.timeout_seconds" :min="10" :max="86400" :step="60" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">立即执行</el-button>
      </template>
    </el-dialog>

    <!-- 任务日志：全屏抽屉 -->
    <el-drawer
      v-model="logVisible"
      fullscreen
      class="log-drawer"
      :title="`任务日志 · ${logTask?.name || ''}`"
      @closed="closeLog"
    >
      <div class="log-page">
        <el-descriptions :column="5" size="small" border class="task-summary">
          <el-descriptions-item label="任务">{{ logTask?.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ typeMeta(logTask?.task_type).label }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag size="small" :type="statusMeta(logStatus).type" effect="dark">{{ statusMeta(logStatus).label }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="触发人">{{ logTask?.triggered_by || '-' }}</el-descriptions-item>
          <el-descriptions-item label="返回码">{{ logTask?.rc ?? '-' }}</el-descriptions-item>
        </el-descriptions>

        <div class="log-tools">
          <span class="muted">共 {{ events.length }} 条事件</span>
          <el-button size="small" :type="autoScroll ? 'primary' : 'default'" plain @click="toggleAutoScroll">
            {{ autoScroll ? '自动滚动中（点击暂停）' : '已暂停自动滚动（点击恢复）' }}
          </el-button>
        </div>

        <div v-loading="logLoading" ref="logBox" class="log-box" @scroll="onScroll">
          <div v-for="ev in events" :key="ev.seq" class="log-line">
            <span class="log-seq">#{{ ev.seq }}</span>
            <el-tag size="small" class="log-level" :type="levelType(ev.level)">{{ ev.level }}</el-tag>
            <span v-if="ev.host" class="log-host">{{ ev.host }}</span>
            <span class="log-msg">{{ ev.message }}</span>
          </div>
          <el-empty v-if="!logLoading && !events.length" description="暂无日志事件" :image-size="80" />
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh } from '@element-plus/icons-vue'
import { WsClient } from '@/api/ws'
import {
  cancelTask,
  createTask,
  deleteTask,
  listHosts,
  listPlaybooks,
  listTaskEvents,
  listTasks,
} from '@/api/modules'

/** 状态元数据：tag 颜色（success 绿 / failed 红 / running 蓝 / canceled 灰 / queued 橙） */
const STATUS_META: Record<string, { label: string; type: string }> = {
  pending: { label: '等待中', type: 'info' },
  queued: { label: '排队中', type: 'warning' },
  running: { label: '运行中', type: 'primary' },
  success: { label: '成功', type: 'success' },
  failed: { label: '失败', type: 'danger' },
  canceled: { label: '已取消', type: 'info' },
  timeout: { label: '超时', type: 'danger' },
}
const STATUS_OPTIONS = Object.entries(STATUS_META).map(([value, m]) => ({ value, label: m.label }))
const ACTIVE_STATUS = ['pending', 'queued', 'running']
const TERMINAL_STATUS = ['success', 'failed', 'canceled', 'timeout']

const TYPE_META: Record<string, { label: string; type: string }> = {
  playbook: { label: '剧本', type: 'primary' },
  adhoc: { label: '临时命令', type: 'success' },
  deploy: { label: '部署', type: 'warning' },
  app_install: { label: 'App安装', type: 'primary' },
  app_uninstall: { label: 'App卸载', type: 'danger' },
}
const TYPE_OPTIONS = Object.entries(TYPE_META).map(([value, m]) => ({ value, label: m.label }))

function statusMeta(s?: string) {
  return STATUS_META[s || ''] || { label: s || '-', type: 'info' }
}
function typeMeta(t?: string) {
  return TYPE_META[t || ''] || { label: t || '-', type: 'info' }
}
function isActive(row: any) {
  return ACTIVE_STATUS.includes(row.status)
}
function isTerminal(row: any) {
  return TERMINAL_STATUS.includes(row.status)
}

// ---------- 列表 ----------
const loading = ref(false)
const list = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(10)
const query = ref({ status: '', task_type: '' })

async function loadList() {
  loading.value = true
  try {
    const resp = await listTasks({
      page: page.value,
      page_size: pageSize.value,
      status: query.value.status || undefined,
      task_type: query.value.task_type || undefined,
    })
    const data = (resp.data as any) || {}
    list.value = data.items || []
    total.value = data.total || 0
  } catch {
    /* 拦截器已提示 */
  } finally {
    loading.value = false
  }
}

function onFilter() {
  page.value = 1
  loadList()
}

// ---------- 新建任务 ----------
const createVisible = ref(false)
const creating = ref(false)
const playbooks = ref<any[]>([])
const hosts = ref<any[]>([])
const form = ref({
  name: '',
  playbook_id: undefined as number | undefined,
  host_ids: [] as number[],
  extra_vars_text: '',
  timeout_seconds: 3600,
})

async function openCreate() {
  form.value = { name: '', playbook_id: undefined, host_ids: [], extra_vars_text: '', timeout_seconds: 3600 }
  createVisible.value = true
  try {
    const [pbResp, hostResp] = await Promise.all([listPlaybooks(), listHosts({ page: 1, page_size: 100 })])
    playbooks.value = (pbResp.data as any) || []
    const allHosts = ((hostResp.data as any)?.items) || []
    hosts.value = allHosts
    // 自动预选：当前 Agent 主机名下的被管主机（host_type != agent）
    const managed = allHosts.filter((h: any) => h.host_type !== 'agent')
    form.value.host_ids = managed.map((h: any) => h.id)
  } catch {
    /* 拦截器已提示 */
  }
}

async function submitCreate() {
  const f = form.value
  if (!f.name.trim()) return ElMessage.warning('请输入任务名称')
  if (!f.playbook_id) return ElMessage.warning('请选择 Playbook')
  if (!f.host_ids.length) return ElMessage.warning('请选择目标主机')

  // extra_vars JSON 容错解析
  let extra_vars: Record<string, any> | undefined
  const text = f.extra_vars_text.trim()
  if (text) {
    try {
      const parsed = JSON.parse(text)
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        return ElMessage.error('extra_vars 必须是 JSON 对象，如 {"key": "value"}')
      }
      extra_vars = parsed
    } catch {
      return ElMessage.error('extra_vars 不是合法的 JSON，请检查格式')
    }
  }

  creating.value = true
  try {
    await createTask({
      name: f.name.trim(),
      playbook_id: f.playbook_id,
      host_ids: f.host_ids,
      extra_vars,
      timeout_seconds: f.timeout_seconds,
    })
    ElMessage.success('任务已创建并进入执行队列')
    createVisible.value = false
    onFilter()
  } catch {
    /* 拦截器已提示 */
  } finally {
    creating.value = false
  }
}

// ---------- 取消 / 删除 ----------
async function onCancel(row: any) {
  try {
    await ElMessageBox.confirm(
      `确定取消任务「${row.name}」？已开始执行的步骤将被中断。`,
      '取消任务',
      { type: 'warning', confirmButtonText: '确认取消', cancelButtonText: '再想想' },
    )
  } catch {
    return
  }
  try {
    await cancelTask(row.id)
    ElMessage.success('已发送取消请求')
    loadList()
  } catch {
    /* 拦截器已提示 */
  }
}

async function onDelete(row: any) {
  try {
    await ElMessageBox.confirm(
      `确定删除任务「${row.name}」？其事件日志将一并删除。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await deleteTask(row.id)
    ElMessage.success('已删除')
    // 删除后修正页码
    const maxPage = Math.max(1, Math.ceil((total.value - 1) / pageSize.value))
    if (page.value > maxPage) page.value = maxPage
    loadList()
  } catch {
    /* 拦截器已提示 */
  }
}

// ---------- 日志抽屉 ----------
const logVisible = ref(false)
const logLoading = ref(false)
const logTask = ref<any>(null)
const logStatus = ref('')
const logBox = ref<HTMLDivElement>()
const events = ref<any[]>([])
const autoScroll = ref(true)
let wsClient: WsClient | null = null
const seenSeq = new Set<number>()

function addEvent(ev: any, resort = true) {
  if (ev.seq == null || seenSeq.has(ev.seq)) return
  seenSeq.add(ev.seq)
  events.value.push({
    seq: ev.seq,
    ts: ev.ts,
    level: ev.level || 'info',
    host: ev.host || '',
    message: ev.message || '',
  })
  if (resort) events.value.sort((a, b) => a.seq - b.seq)
}

async function openLog(row: any) {
  logTask.value = row
  logStatus.value = row.status
  seenSeq.clear()
  events.value = []
  autoScroll.value = true
  logVisible.value = true

  // 1) 先拉历史事件
  logLoading.value = true
  try {
    const resp = await listTaskEvents(row.id)
    for (const ev of (resp.data as any) || []) addEvent(ev, false)
    events.value.sort((a, b) => a.seq - b.seq)
  } catch {
    /* 拦截器已提示 */
  } finally {
    logLoading.value = false
    nextTick(scrollToBottom)
  }

  // 2) WS 实时追加（连接时服务端会补发历史，按 seq 去重）
  connectWs(row.id)
}

function connectWs(taskId: number) {
  wsClient?.close()
  wsClient = new WsClient(`/api/v1/ws/tasks/${taskId}/logs`, onWsMessage)
  wsClient.connect()
}

function onWsMessage(msg: any) {
  if (!msg || typeof msg !== 'object') return
  if (msg.type === 'task_event') {
    addEvent(msg)
    if (autoScroll.value) nextTick(scrollToBottom)
  } else if (msg.type === 'task_status') {
    logStatus.value = msg.status
    const row = list.value.find((t: any) => t.id === msg.task_id)
    if (row) row.status = msg.status
  }
}

function onScroll(e: Event) {
  const el = e.target as HTMLElement
  // 距底部 60px 内视为"贴底"，保持自动滚动；用户上翻则暂停
  autoScroll.value = el.scrollHeight - el.scrollTop - el.clientHeight < 60
}

function scrollToBottom() {
  const el = logBox.value
  if (el) el.scrollTop = el.scrollHeight
}

function toggleAutoScroll() {
  autoScroll.value = !autoScroll.value
  if (autoScroll.value) nextTick(scrollToBottom)
}

function closeLog() {
  wsClient?.close()
  wsClient = null
  seenSeq.clear()
  events.value = []
  logTask.value = null
  logStatus.value = ''
  // 任务状态可能已变化，静默刷新列表
  loadList()
}

/** 日志级别 tag：error 红 / warn 橙 / info 默认 */
function levelType(level: string): string {
  if (level === 'error') return 'danger'
  if (level === 'warn' || level === 'warning') return 'warning'
  if (level === 'debug') return 'info'
  return 'primary'
}

// ---------- 展示辅助 ----------
function fmtTime(v: any): string {
  if (!v) return '-'
  return String(v).replace('T', ' ').slice(0, 19)
}
function fmtDuration(ms: any): string {
  if (ms == null) return '-'
  const n = Number(ms)
  if (n < 1000) return `${n}ms`
  const s = n / 1000
  if (s < 60) return `${s.toFixed(1)}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m${Math.round(s % 60)}s`
  const h = Math.floor(m / 60)
  return `${h}h${m % 60}m`
}

// ---------- 生命周期 ----------
let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  loadList()
  // 存在未完成任务时 10s 轮询状态
  pollTimer = setInterval(() => {
    if (list.value.some((t) => isActive(t))) loadList()
  }, 10000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
  wsClient?.close()
  wsClient = null
})
</script>

<style scoped>
.task-page .table-card { min-height: 200px; }
.card-header { display: flex; align-items: center; justify-content: space-between; }
.filters { display: flex; align-items: center; gap: 10px; }
.pager { margin-top: 14px; justify-content: flex-end; }
.muted { color: #c0c4cc; }

/* 日志抽屉 */
.log-drawer :deep(.el-drawer__body) {
  display: flex;
  padding: 12px 16px 16px;
  overflow: hidden;
}
.log-page { flex: 1; display: flex; flex-direction: column; gap: 10px; min-height: 0; }
.task-summary { flex-shrink: 0; }
.log-tools { display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }

.log-box {
  flex: 1;
  min-height: 0;
  overflow: auto;
  border: 1px solid #e4e7ed;
  border-radius: 6px;
  background: #fafbfd;
  padding: 8px 10px;
}
.log-line {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 3px 2px;
  border-bottom: 1px dashed #f0f2f5;
  font-size: 12px;
  line-height: 20px;
}
.log-seq { color: #c0c4cc; width: 52px; flex-shrink: 0; text-align: right; }
.log-level { flex-shrink: 0; }
.log-host {
  color: #409eff;
  flex-shrink: 0;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.log-msg {
  flex: 1;
  white-space: pre-wrap;
  word-break: break-all;
  color: #303133;
}
</style>
