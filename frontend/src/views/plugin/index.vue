<template>
  <el-card shadow="never">
    <div class="toolbar">
      <el-input
        v-model="keyword"
        placeholder="按名称搜索"
        clearable
        style="width: 220px"
        @keyup.enter="load"
        @clear="load"
      />
      <el-button @click="load">搜索</el-button>
      <el-button v-permission="'plugin:create'" type="primary" @click="openCreate">新增插件</el-button>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="name" label="名称" min-width="150" show-overflow-tooltip />
      <el-table-column label="类型" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="row.plugin_type === 'role' ? 'warning' : 'success'" size="small">
            {{ row.plugin_type === 'role' ? 'Role' : 'Collection' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="source" label="来源" min-width="200" show-overflow-tooltip />
      <el-table-column prop="version" label="版本" width="90">
        <template #default="{ row }">{{ row.version || '-' }}</template>
      </el-table-column>
      <el-table-column label="安装状态" width="110" align="center">
        <template #default="{ row }">
          <el-tag :type="statusMap[row.install_status]?.type || 'info'" size="small">
            {{ statusMap[row.install_status]?.label || row.install_status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button
            v-permission="'plugin:install'"
            link
            type="primary"
            :disabled="row.install_status === 'installing'"
            @click="onInstall(row)"
          >安装</el-button>
          <el-button link @click="onShowLog(row)">安装日志</el-button>
          <el-button v-permission="'plugin:install'" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-permission="'plugin:delete'" link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="isCreate ? '新增插件' : '编辑插件'" width="520px" destroy-on-close>
      <el-form :model="form" label-width="90px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" :disabled="!isCreate" placeholder="插件名称" />
        </el-form-item>
        <el-form-item label="类型" required>
          <el-select v-model="form.plugin_type" :disabled="!isCreate" style="width: 100%">
            <el-option label="Collection" value="collection" />
            <el-option label="Role" value="role" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源" required>
          <el-input
            v-model="form.source"
            :disabled="!isCreate"
            :placeholder="form.plugin_type === 'role' ? 'galaxy 名称或 git URL' : '如 community.docker'"
          />
        </el-form-item>
        <el-form-item label="版本">
          <el-input v-model="form.version" placeholder="留空则默认版本" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="用途说明" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="logVisible" :title="`安装日志 - ${logRow?.name || ''}`" width="720px">
      <pre class="log">{{ logRow?.install_log || '暂无安装日志' }}</pre>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createPlugin, deletePlugin, installPlugin, listPlugins, updatePlugin } from '@/api/modules'

const loading = ref(false)
const saving = ref(false)
const rows = ref<any[]>([])
const keyword = ref('')

const dialogVisible = ref(false)
const isCreate = ref(true)
const editId = ref(0)
const form = reactive<any>({
  name: '',
  plugin_type: 'collection',
  source: '',
  version: '',
  description: '',
})

const logVisible = ref(false)
const logRow = ref<any>(null)

const statusMap: Record<string, { label: string; type: string }> = {
  installed: { label: '已安装', type: 'success' },
  installing: { label: '安装中', type: 'primary' },
  failed: { label: '安装失败', type: 'danger' },
  none: { label: '未安装', type: 'info' },
}

let pollTimer: ReturnType<typeof setInterval> | null = null

function fmtTime(v?: string) {
  if (!v) return '-'
  return String(v).replace('T', ' ').slice(0, 19)
}

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    const resp = await listPlugins(keyword.value || undefined)
    rows.value = (resp.data as any[]) || []
  } finally {
    if (!silent) loading.value = false
  }
}

/** 每 30s 刷新一次，直到没有 installing 状态的插件 */
function startPolling() {
  stopPolling()
  pollTimer = setInterval(async () => {
    await load(true)
    if (!rows.value.some((r) => r.install_status === 'installing')) {
      stopPolling()
      ElMessage.success('插件安装状态已更新')
    }
  }, 30000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function openCreate() {
  isCreate.value = true
  Object.assign(form, { name: '', plugin_type: 'collection', source: '', version: '', description: '' })
  dialogVisible.value = true
}

function openEdit(row: any) {
  isCreate.value = false
  editId.value = row.id
  Object.assign(form, {
    name: row.name,
    plugin_type: row.plugin_type,
    source: row.source,
    version: row.version || '',
    description: row.description || '',
  })
  dialogVisible.value = true
}

async function onSave() {
  if (!form.name.trim()) return ElMessage.warning('请输入插件名称')
  if (!form.source.trim()) return ElMessage.warning('请输入插件来源')
  saving.value = true
  try {
    if (isCreate.value) {
      await createPlugin({
        name: form.name.trim(),
        plugin_type: form.plugin_type,
        source: form.source.trim(),
        version: form.version.trim(),
        description: form.description,
      })
      ElMessage.success('插件已创建')
    } else {
      await updatePlugin(editId.value, {
        version: form.version.trim(),
        description: form.description,
      })
      ElMessage.success('插件已更新')
    }
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function onInstall(row: any) {
  const resp = await installPlugin(row.id)
  const updated = resp.data as any
  if (updated) Object.assign(row, updated)
  ElMessage.success('插件正在后台安装，状态稍后自动刷新')
  startPolling()
}

function onShowLog(row: any) {
  logRow.value = row
  logVisible.value = true
}

async function onDelete(row: any) {
  const ok = await ElMessageBox.confirm(`确认删除插件「${row.name}」？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).then(() => true).catch(() => false)
  if (!ok) return
  await deletePlugin(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
onUnmounted(stopPolling)
</script>

<style scoped>
.toolbar { margin-bottom: 14px; display: flex; gap: 10px; }
.log {
  max-height: 420px;
  overflow: auto;
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 12px;
  border-radius: 4px;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  margin: 0;
}
</style>
