<template>
  <div class="playbook-page">
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span>Playbook 文件（{{ scanRootLabel || '未选择 Agent 主机' }}）</span>
          <div>
            <el-button :icon="Refresh" size="small" @click="loadScan">刷新</el-button>
            <el-button type="primary" :icon="Plus" size="small" @click="openCreate">新增 YAML</el-button>
          </div>
        </div>
      </template>

      <el-table :data="scanList" v-loading="scanLoading" size="small">
        <el-table-column prop="name" label="文件名" width="200" show-overflow-tooltip />
        <el-table-column prop="path" label="完整路径" min-width="300" show-overflow-tooltip />
        <el-table-column prop="agent_hostname" label="所属 Agent 主机" width="160" />
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEditor(row)">编辑</el-button>
            <el-button link type="success" @click="onDebug(row)">调试</el-button>
            <el-button link type="danger" @click="onDelete(row)">删除</el-button>
          </template>
        </el-table-column>
        <template #empty><el-empty description="未扫描到 playbook 文件，请先新增" /></template>
      </el-table>
    </el-card>

    <!-- 新增 YAML -->
    <el-dialog v-model="createVisible" title="新增 YAML" width="660px" :close-on-click-modal="false">
      <el-form label-width="90px">
        <el-form-item label="文件名" required>
          <el-input v-model="createForm.name" placeholder="如：deploy.yml" maxlength="128" />
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="createForm.content" type="textarea" :rows="12" spellcheck="false" class="code-area"
            :placeholder="TEMPLATE" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onCreate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 编辑 YAML -->
    <el-dialog v-model="editVisible" title="编辑 YAML" width="760px" :close-on-click-modal="false">
      <div class="edit-path">{{ editRow?.path }}</div>
      <el-input v-model="editContent" type="textarea" :rows="18" spellcheck="false" class="code-area" />
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSaveEdit">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Plus, Refresh } from '@element-plus/icons-vue'
import request from '@/api/request'

const TEMPLATE = `- hosts: all
  tasks:
    - name: 示例任务
      command: echo hello
`

const scanList = ref<any[]>([])
const scanLoading = ref(false)
const scanRootLabel = ref('')

// 新增
const createVisible = ref(false)
const createForm = ref({ name: '', content: '' })
const saving = ref(false)

// 编辑
const editVisible = ref(false)
const editRow = ref<any>(null)
const editContent = ref('')

async function loadScan() {
  scanLoading.value = true
  try {
    const resp = await request.get('/playbooks/scan')
    scanList.value = (resp.data as any) || []
    if (scanList.value.length) {
      scanRootLabel.value = scanList.value[0].path.replace(/\/[^/]+$/, '')
    }
  } catch { /* 拦截器已提示 */ } finally {
    scanLoading.value = false
  }
}

function openCreate() {
  createForm.value = { name: '', content: TEMPLATE }
  createVisible.value = true
}

async function onCreate() {
  if (!createForm.value.name.trim()) return ElMessage.warning('请输入文件名')
  saving.value = true
  try {
    await request.post('/playbooks/write-file', {
      path: createForm.value.name.trim(),
      content: createForm.value.content,
    })
    ElMessage.success('创建成功')
    createVisible.value = false
    loadScan()
  } finally { saving.value = false }
}

async function openEditor(row: any) {
  editRow.value = row
  try {
    const resp = await request.get('/playbooks/read-file', { params: { path: row.path } })
    editContent.value = (resp.data as any)?.content || ''
    editVisible.value = true
  } catch { ElMessage.error('读取文件失败') }
}

async function onSaveEdit() {
  saving.value = true
  try {
    await request.post('/playbooks/write-file', { path: editRow.value.path, content: editContent.value })
    ElMessage.success('保存成功')
    editVisible.value = false
  } finally { saving.value = false }
}

async function onDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除文件「${row.name}」？删除后不可恢复。`, '删除确认', { type: 'warning' })
  } catch { return }
  try {
    await request.delete('/playbooks/file', { params: { path: row.path } })
    ElMessage.success('已删除')
    loadScan()
  } catch { /* 拦截器已提示 */ }
}

async function onDebug(row: any) {
  ElMessage.info(`正在调试 ${row.name}...`)
  try {
    const resp = await request.post('/playbooks/debug', { path: row.path })
    const d = resp.data as any
    if (d?.rc === 0) ElMessage.success(`调试成功：${row.name}`)
    else ElMessage.warning(`调试完成（rc=${d?.rc}）`)
    await ElMessageBox.alert(
      `<pre style="max-height:400px;overflow:auto;font-size:12px">${(d?.stdout || '').replace(/</g, '&lt;')}</pre>`,
      `调试结果 ${row.name}（rc=${d?.rc}）`,
      { dangerouslyUseHTMLString: true }
    )
  } catch { ElMessage.error('调试失败') }
}

onMounted(loadScan)
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.code-area { font-family: monospace; }
.edit-path { font-size: 12px; color: #909399; margin-bottom: 8px; word-break: break-all; }
</style>
