<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span class="card-title">项目管理</span>
        <el-button v-permission="'project:create'" type="primary" :icon="Plus" @click="openCreate">
          新增项目
        </el-button>
      </div>
    </template>

    <el-table :data="list" v-loading="loading" row-key="id">
      <el-table-column prop="name" label="项目名称" min-width="140" show-overflow-tooltip />
      <el-table-column prop="code" label="项目编码" width="140" show-overflow-tooltip />
      <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">
            {{ row.status === 'active' ? '启用' : '归档' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'project:update'" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-permission="'project:delete'" link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialog.visible" :title="dialog.isEdit ? '编辑项目' : '新增项目'" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="项目名称" prop="name">
          <el-input v-model="form.name" placeholder="如：订单中心" maxlength="64" />
        </el-form-item>
        <el-form-item label="项目编码" prop="code">
          <el-input
            v-model="form.code"
            placeholder="字母 / 数字 / 下划线 / 中划线"
            maxlength="64"
            :disabled="dialog.isEdit"
          />
        </el-form-item>
        <el-form-item label="描述" prop="description">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="项目描述（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取 消</el-button>
        <el-button type="primary" :loading="dialog.saving" @click="onSave">确 定</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { listProjects, createProject, updateProject, deleteProject } from '@/api/modules'

const loading = ref(false)
const list = ref<any[]>([])
const formRef = ref<FormInstance>()

const dialog = reactive({ visible: false, isEdit: false, saving: false, id: 0 })
const form = reactive({ name: '', code: '', description: '' })

const rules: FormRules = {
  name: [{ required: true, message: '请输入项目名称', trigger: 'blur' }],
  code: [
    { required: true, message: '请输入项目编码', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_-]+$/, message: '仅支持字母、数字、下划线、中划线', trigger: 'blur' },
  ],
}

function fmtTime(t: any) {
  if (!t) return '-'
  return String(t).replace('T', ' ').slice(0, 19)
}

async function load() {
  loading.value = true
  try {
    const resp = await listProjects()
    list.value = (resp.data as any[]) || []
  } finally {
    loading.value = false
  }
}

function openCreate() {
  dialog.isEdit = false
  dialog.id = 0
  form.name = ''
  form.code = ''
  form.description = ''
  dialog.visible = true
}

function openEdit(row: any) {
  dialog.isEdit = true
  dialog.id = row.id
  form.name = row.name
  form.code = row.code
  form.description = row.description || ''
  dialog.visible = true
}

async function onSave() {
  if (!formRef.value) return
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return
  dialog.saving = true
  try {
    if (dialog.isEdit) {
      await updateProject(dialog.id, { name: form.name, description: form.description })
      ElMessage.success('修改成功')
    } else {
      await createProject({ name: form.name, code: form.code, description: form.description })
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

async function onDelete(row: any) {
  try {
    await ElMessageBox.confirm(`确认删除项目「${row.name}」？删除后不可恢复。`, '删除确认', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await deleteProject(row.id)
    ElMessage.success('已删除')
    load()
  } catch {
    /* 拦截器已提示 */
  }
}

onMounted(load)
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
</style>
