<template>
  <el-card shadow="never">
    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="按名称/代码搜索"
        clearable
        style="width: 220px"
        @keyup.enter="load"
        @clear="load"
      />
      <el-button @click="load">搜索</el-button>
      <el-button v-permission="'deploy:create'" type="primary" @click="openCreate">新增部署工程</el-button>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="name" label="名称" min-width="130" show-overflow-tooltip />
      <el-table-column prop="code" label="代码" width="110" />
      <el-table-column label="镜像" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">{{ imageOf(row) }}</template>
      </el-table-column>
      <el-table-column label="运行时" width="90" align="center">
        <template #default="{ row }">
          <el-tag size="small" effect="plain">{{ row.runtime }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="主机数" width="80" align="center">
        <template #default="{ row }">{{ (row.host_ids || []).length }}</template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="330" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'deploy:run'" link type="primary" @click="onDeploy(row)">部署</el-button>
          <el-button v-permission="'deploy:rollback'" link type="warning" @click="onRollback(row)">回滚</el-button>
          <el-button v-permission="'deploy:run'" link @click="onAction(row, 'restart', '重启')">重启</el-button>
          <el-button v-permission="'deploy:run'" link @click="onAction(row, 'stop', '停止')">停止</el-button>
          <el-button v-permission="'deploy:run'" link @click="onAction(row, 'start', '启动')">启动</el-button>
          <el-button link type="info" @click="openRecords(row)">记录</el-button>
          <el-button v-permission="'deploy:update'" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-permission="'deploy:delete'" link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增 / 编辑 -->
    <el-dialog v-model="dialogVisible" :title="isCreate ? '新增部署工程' : '编辑部署工程'" width="720px" destroy-on-close>
      <el-form :model="form" label-width="110px">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="名称" required>
              <el-input v-model="form.name" placeholder="工程名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="代码" required>
              <el-input v-model="form.code" :disabled="!isCreate" placeholder="字母数字_-，如 web-app" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="所属项目">
              <el-select v-model="form.project_id" clearable placeholder="选择项目（可选）" style="width: 100%">
                <el-option v-for="p in projects" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="Registry">
              <el-input v-model="form.registry_url" placeholder="如 registry.example.com（可选）" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="14">
            <el-form-item label="镜像仓库" required>
              <el-input v-model="form.image_repo" placeholder="如 registry.example.com/myapp" />
            </el-form-item>
          </el-col>
          <el-col :span="10">
            <el-form-item label="默认Tag">
              <el-input v-model="form.default_tag" placeholder="latest" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="镜像来源">
              <el-radio-group v-model="form.build_type">
                <el-radio value="">镜像仓库拉取</el-radio>
                <el-radio value="docker">Docker 构建</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item v-if="form.build_type === 'docker'" label="构建主机">
              <el-select v-model="form.build_host_id" placeholder="装有 Docker 服务的主机" style="width: 100%">
                <el-option v-for="h in hostOptions" :key="h.id" :label="`${h.hostname} (${h.ip})`" :value="h.id" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        <template v-if="form.build_type === 'docker'">
          <el-row :gutter="16">
            <el-col :span="12">
              <el-form-item label="构建上下文">
                <el-input v-model="form.build_context" placeholder="构建主机上的路径，如 /opt/src/myapp" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="Dockerfile">
                <el-input v-model="form.dockerfile" placeholder="Dockerfile（相对上下文）" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-form-item label="构建参数">
            <el-input v-model="form.build_args" type="textarea" :rows="2" placeholder='JSON，如 {"VERSION":"1.0"}，可选' />
          </el-form-item>
        </template>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="容器运行时">
              <el-radio-group v-model="form.runtime">
                <el-radio value="nerdctl">nerdctl</el-radio>
                <el-radio value="ctr">ctr</el-radio>
              </el-radio-group>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="命名空间">
              <el-input v-model="form.namespace" placeholder="k8s.io" />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="环境变量">
          <el-input v-model="form.env" type="textarea" :rows="3" placeholder='JSON，如 {"TZ":"Asia/Shanghai"}，留空则不设置' />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="端口映射">
              <el-input v-model="form.ports" type="textarea" :rows="3" placeholder='JSON，如 {"80":"8080"}' />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="挂载">
              <el-input v-model="form.mounts" type="textarea" :rows="3" placeholder='JSON，如 {"/data":"/data/app"}' />
            </el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="健康检查">
          <el-input
            v-model="form.healthcheck"
            type="textarea"
            :rows="3"
            placeholder='JSON，如 {"type":"tcp","port":80,"delay":30}'
          />
        </el-form-item>
        <el-form-item label="允许回滚">
          <el-switch v-model="form.rollback_enabled" />
        </el-form-item>
        <el-form-item label="部署主机" required>
          <el-select
            v-model="form.host_ids"
            multiple
            filterable
            placeholder="选择部署目标主机（可多选）"
            style="width: 100%"
            @change="onHostsChange"
          >
            <el-option
              v-for="h in hostOptions"
              :key="h.id"
              :label="`${h.hostname}（${h.ip}）`"
              :value="h.id"
            />
          </el-select>
          <div class="form-tip">容器名默认取「代码」；编辑时可保留原有容器名</div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <!-- 部署记录 -->
    <el-drawer v-model="drawerVisible" size="62%" :title="`部署记录 - ${recordRow?.name || ''}`">
      <el-table v-loading="recordLoading" :data="records" border size="small">
        <el-table-column prop="image_tag" label="镜像Tag" min-width="100" />
        <el-table-column label="动作" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="actionMap[row.action]?.type || 'info'" size="small">
              {{ actionMap[row.action]?.label || row.action }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">{{ statusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="triggered_by" label="触发人" width="100" />
        <el-table-column label="开始时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.started_at) }}</template>
        </el-table-column>
        <el-table-column label="结束时间" width="160">
          <template #default="{ row }">{{ fmtTime(row.finished_at) }}</template>
        </el-table-column>
        <el-table-column label="任务" width="90" align="center">
          <template #default="{ row }">
            <el-button v-if="row.task_id" link type="primary" @click="onTaskClick(row.task_id)">
              #{{ row.task_id }}
            </el-button>
            <span v-else>-</span>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        class="pager"
        background
        layout="total, prev, pager, next"
        :total="recordTotal"
        :current-page="recordPage"
        :page-size="recordPageSize"
        @current-change="onRecordPage"
      />
    </el-drawer>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'
import {
  createDeployProject, deleteDeployProject, deployProject, getDeployProject,
  listDeployProjects, listDeployRecords, listHosts, listProjects, updateDeployProject,
} from '@/api/modules'

const router = useRouter()

const loading = ref(false)
const saving = ref(false)
const rows = ref<any[]>([])
const keyword = ref('')
const projects = ref<any[]>([])
const hostOptions = ref<any[]>([])

const dialogVisible = ref(false)
const isCreate = ref(true)
const editId = ref(0)
/** host_id → {container_name, enabled} */
const hostDetails = ref<Record<number, { container_name: string; enabled: boolean }>>({})
const form = reactive<any>({
  name: '',
  code: '',
  project_id: null as number | null,
  registry_url: '',
  image_repo: '',
  default_tag: 'latest',
  build_type: '',
  build_host_id: null as number | null,
  build_context: '',
  dockerfile: 'Dockerfile',
  build_args: '',
  runtime: 'nerdctl',
  namespace: 'k8s.io',
  env: '',
  ports: '',
  mounts: '',
  healthcheck: '',
  rollback_enabled: true,
  host_ids: [] as number[],
})

const drawerVisible = ref(false)
const recordRow = ref<any>(null)
const recordLoading = ref(false)
const records = ref<any[]>([])
const recordTotal = ref(0)
const recordPage = ref(1)
const recordPageSize = ref(10)

const actionMap: Record<string, { label: string; type: string }> = {
  deploy: { label: '部署', type: 'primary' },
  rollback: { label: '回滚', type: 'warning' },
  restart: { label: '重启', type: 'info' },
  stop: { label: '停止', type: 'danger' },
  start: { label: '启动', type: 'success' },
}

const STATUS_MAP: Record<string, { label: string; type: string }> = {
  pending: { label: '等待中', type: 'info' },
  queued: { label: '排队中', type: 'info' },
  running: { label: '执行中', type: 'primary' },
  success: { label: '成功', type: 'success' },
  failed: { label: '失败', type: 'danger' },
  canceled: { label: '已取消', type: 'warning' },
}

function statusType(s: string) {
  return STATUS_MAP[s]?.type || 'info'
}

function statusLabel(s: string) {
  return STATUS_MAP[s]?.label || s || '-'
}

function fmtTime(v?: string) {
  if (!v) return '-'
  return String(v).replace('T', ' ').slice(0, 19)
}

function imageOf(row: any) {
  return `${row.image_repo || '-'}:${row.default_tag || '-'}`
}

/** JSON 容错解析：空串 → null；非法 JSON → undefined（由调用方中断） */
function safeParse(text: string, label: string): any {
  if (!text || !text.trim()) return null
  try {
    return JSON.parse(text)
  } catch {
    ElMessage.error(`${label} 不是合法的 JSON，请检查格式`)
    return undefined
  }
}

function toText(v: any) {
  if (v === null || v === undefined) return ''
  return JSON.stringify(v, null, 2)
}

async function load() {
  loading.value = true
  try {
    const resp = await listDeployProjects(keyword.value || undefined)
    rows.value = (resp.data as any[]) || []
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  const [projResp, hostResp] = await Promise.all([listProjects(), listHosts({ page_size: 100 })])
  projects.value = (projResp.data as any[]) || []
  hostOptions.value = ((hostResp.data as any)?.items || []) as any[]
}

function openCreate() {
  isCreate.value = true
  editId.value = 0
  hostDetails.value = {}
  Object.assign(form, {
    name: '', code: '', project_id: null, registry_url: '', image_repo: '',
    default_tag: 'latest', build_type: '', build_host_id: null, build_context: '',
    dockerfile: 'Dockerfile', build_args: '',
    runtime: 'nerdctl', namespace: 'k8s.io',
    env: '', ports: '', mounts: '', healthcheck: '', rollback_enabled: true, host_ids: [],
  })
  // 自动预选：当前 Agent 主机名下的被管主机
  const managed = hostOptions.value.filter((h: any) => h.host_type !== 'agent')
  form.host_ids = managed.map((h: any) => h.id)
  dialogVisible.value = true
}

async function openEdit(row: any) {
  isCreate.value = false
  editId.value = row.id
  const resp = await getDeployProject(row.id)
  const p = resp.data as any
  Object.assign(form, {
    name: p.name,
    code: p.code,
    project_id: p.project_id ?? null,
    registry_url: p.registry_url || '',
    image_repo: p.image_repo || '',
    default_tag: p.default_tag || 'latest',
    build_type: p.build_type || '',
    build_host_id: p.build_host_id ?? null,
    build_context: p.build_context || '',
    dockerfile: p.dockerfile || 'Dockerfile',
    build_args: toText(p.build_args),
    runtime: p.runtime || 'nerdctl',
    namespace: p.namespace || 'k8s.io',
    env: toText(p.env),
    ports: toText(p.ports),
    mounts: toText(p.mounts),
    healthcheck: toText(p.healthcheck),
    rollback_enabled: !!p.rollback_enabled,
    host_ids: (p.hosts || []).map((h: any) => h.host_id),
  })
  hostDetails.value = {}
  for (const h of p.hosts || []) {
    hostDetails.value[h.host_id] = { container_name: h.container_name || '', enabled: !!h.enabled }
  }
  dialogVisible.value = true
}

function onHostsChange(ids: number[]) {
  for (const id of ids) {
    if (!hostDetails.value[id]) {
      hostDetails.value[id] = { container_name: form.code || '', enabled: true }
    }
  }
}

function buildHosts() {
  return form.host_ids.map((id: number) => ({
    host_id: id,
    container_name: hostDetails.value[id]?.container_name || form.code || '',
    enabled: hostDetails.value[id]?.enabled ?? true,
  }))
}

async function onSave() {
  if (!form.name.trim()) return ElMessage.warning('请输入工程名称')
  if (!/^[a-zA-Z0-9_-]+$/.test(form.code.trim())) return ElMessage.warning('代码仅允许字母、数字、下划线和中划线')
  if (!form.image_repo.trim()) return ElMessage.warning('请输入镜像仓库')
  if (!form.host_ids.length) return ElMessage.warning('请选择部署主机')

  const env = safeParse(form.env, '环境变量')
  if (env === undefined) return
  const ports = safeParse(form.ports, '端口映射')
  if (ports === undefined) return
  const mounts = safeParse(form.mounts, '挂载')
  if (mounts === undefined) return
  const healthcheck = safeParse(form.healthcheck, '健康检查')
  if (healthcheck === undefined) return
  const build_args = safeParse(form.build_args, '构建参数')
  if (build_args === undefined) return
  if (form.build_type === 'docker') {
    if (!form.build_host_id) return ElMessage.warning('Docker 构建需要选择构建主机')
    if (!form.build_context.trim()) return ElMessage.warning('请输入构建上下文路径')
  }

  saving.value = true
  try {
    const payload = {
      name: form.name.trim(),
      code: form.code.trim(),
      project_id: form.project_id || null,
      registry_url: form.registry_url.trim(),
      image_repo: form.image_repo.trim(),
      default_tag: form.default_tag.trim() || 'latest',
      build_type: form.build_type || '',
      build_host_id: form.build_type === 'docker' ? form.build_host_id : null,
      build_context: form.build_type === 'docker' ? form.build_context.trim() : '',
      dockerfile: form.build_type === 'docker' ? (form.dockerfile.trim() || 'Dockerfile') : 'Dockerfile',
      build_args: form.build_type === 'docker' ? build_args : null,
      runtime: form.runtime,
      namespace: form.namespace.trim() || 'k8s.io',
      env, ports, mounts, healthcheck,
      rollback_enabled: form.rollback_enabled,
      hosts: buildHosts(),
    }
    if (isCreate.value) {
      await createDeployProject(payload)
      ElMessage.success('部署工程已创建')
    } else {
      await updateDeployProject(editId.value, payload)
      ElMessage.success('部署工程已更新')
    }
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

// ---- 部署动作 ----

async function onDeploy(row: any) {
  let tag = ''
  try {
    const res = await ElMessageBox.prompt(
      `镜像 Tag 留空则使用默认 Tag「${row.default_tag || 'latest'}」`,
      `部署 - ${row.name}`,
      {
        confirmButtonText: '开始部署',
        cancelButtonText: '取消',
        inputValue: '',
        inputPlaceholder: row.default_tag || 'latest',
      },
    )
    tag = ((res as any).value || '').trim()
  } catch {
    return
  }
  await deployProject(row.id, 'deploy', { image_tag: tag })
  ElMessage.success('部署任务已提交，请稍后在部署记录中查看进度')
  openRecords(row)
}

async function onRollback(row: any) {
  let tag = ''
  try {
    const res = await ElMessageBox.prompt('请输入要回滚到的目标镜像 Tag', `回滚 - ${row.name}`, {
      confirmButtonText: '开始回滚',
      cancelButtonText: '取消',
      inputPlaceholder: '目标镜像 Tag，必填',
      inputValidator: (v: string) => !!v?.trim() || '请输入目标镜像 Tag',
    })
    tag = ((res as any).value || '').trim()
  } catch {
    return
  }
  await deployProject(row.id, 'rollback', { image_tag: tag })
  ElMessage.success('回滚任务已提交，请稍后在部署记录中查看进度')
  openRecords(row)
}

async function onAction(row: any, action: string, label: string) {
  const ok = await ElMessageBox.confirm(
    `确认对工程「${row.name}」的所有主机容器执行【${label}】操作？`,
    label,
    { type: 'warning', confirmButtonText: label, cancelButtonText: '取消' },
  ).then(() => true).catch(() => false)
  if (!ok) return
  await deployProject(row.id, action)
  ElMessage.success(`${label}任务已提交`)
}

async function onDelete(row: any) {
  const ok = await ElMessageBox.confirm(`确认删除部署工程「${row.name}」？删除后不可恢复`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).then(() => true).catch(() => false)
  if (!ok) return
  await deleteDeployProject(row.id)
  ElMessage.success('已删除')
  load()
}

// ---- 部署记录 ----

async function loadRecords() {
  if (!recordRow.value) return
  recordLoading.value = true
  try {
    const resp = await listDeployRecords({
      deploy_project_id: recordRow.value.id,
      page: recordPage.value,
      page_size: recordPageSize.value,
    })
    const data = resp.data as any
    records.value = data.items || []
    recordTotal.value = data.total || 0
  } finally {
    recordLoading.value = false
  }
}

function openRecords(row: any) {
  recordRow.value = row
  recordPage.value = 1
  drawerVisible.value = true
  loadRecords()
}

function onRecordPage(p: number) {
  recordPage.value = p
  loadRecords()
}

async function onTaskClick(taskId: number) {
  const go = await ElMessageBox.confirm(
    `任务 ID：${taskId}，是否跳转到「任务管理」查看详情？`,
    '查看任务',
    { type: 'info', confirmButtonText: '前往查看', cancelButtonText: '取消' },
  ).then(() => true).catch(() => false)
  if (go) router.push('/task')
}

onMounted(() => {
  load()
  loadOptions()
})
</script>

<style scoped>
.toolbar { margin-bottom: 14px; display: flex; gap: 10px; }
.form-tip { color: #909399; font-size: 12px; line-height: 1.6; margin-top: 2px; }
.pager { margin-top: 12px; justify-content: flex-end; }
</style>
