<template>
  <el-card shadow="never">
    <div class="toolbar">
      <el-button v-permission="'role:create'" type="primary" @click="openCreate">新增角色</el-button>
    </div>

    <el-table v-loading="loading" :data="roles" border stripe>
      <el-table-column prop="name" label="角色名称" min-width="130" />
      <el-table-column prop="code" label="角色编码" min-width="120" />
      <el-table-column prop="description" label="描述" min-width="180" show-overflow-tooltip />
      <el-table-column label="启用" width="90" align="center">
        <template #default="{ row }">
          <el-switch v-model="row.enabled" @change="onToggleEnabled(row)" />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'role:update'" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-permission="'role:delete'" link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="isCreate ? '新增角色' : '编辑角色'"
      width="560px"
      destroy-on-close
      @opened="onDialogOpened"
    >
      <el-form :model="form" label-width="80px">
        <el-form-item label="角色名称" required>
          <el-input v-model="form.name" placeholder="如：运维工程师" />
        </el-form-item>
        <el-form-item label="角色编码" required>
          <el-input v-model="form.code" :disabled="!isCreate" placeholder="如：ops" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="2" placeholder="角色说明" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item label="菜单权限">
          <div class="tree-box">
            <el-tree
              ref="treeRef"
              :data="menus"
              show-checkbox
              node-key="id"
              :props="{ label: 'name' }"
              default-expand-all
              :empty-text="'暂无菜单'"
            />
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="onSave">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createRole, deleteRole, listRoles, menuTree, updateRole } from '@/api/modules'

const loading = ref(false)
const saving = ref(false)
const roles = ref<any[]>([])
const menus = ref<any[]>([])
const treeRef = ref<any>(null)
/** 弹窗打开后需要勾选的节点（叶子） */
const pendingKeys = ref<number[]>([])

const dialogVisible = ref(false)
const isCreate = ref(true)
const editId = ref(0)
const form = reactive<any>({
  name: '',
  code: '',
  description: '',
  enabled: true,
})

async function load() {
  loading.value = true
  try {
    const resp = await listRoles()
    roles.value = (resp.data as any[]) || []
  } finally {
    loading.value = false
  }
}

async function loadMenus() {
  const resp = await menuTree()
  menus.value = (resp.data as any[]) || []
}

/** 树中「有子节点」的 id 集合 */
function parentIdsOfTree(): Set<number> {
  const parents = new Set<number>()
  const walk = (nodes: any[]) => {
    for (const n of nodes) {
      if (n.children && n.children.length) {
        parents.add(n.id)
        walk(n.children)
      }
    }
  }
  walk(menus.value)
  return parents
}

function openCreate() {
  isCreate.value = true
  Object.assign(form, { name: '', code: '', description: '', enabled: true })
  pendingKeys.value = []
  dialogVisible.value = true
}

function openEdit(row: any) {
  isCreate.value = false
  editId.value = row.id
  Object.assign(form, {
    name: row.name,
    code: row.code,
    description: row.description || '',
    enabled: !!row.enabled,
  })
  // 只勾选叶子节点，父节点由 el-tree 联动（否则 setCheckedKeys 会把父节点下所有子节点全部勾上）
  const parents = parentIdsOfTree()
  pendingKeys.value = (row.menu_ids || []).filter((id: number) => !parents.has(id))
  dialogVisible.value = true
}

function onDialogOpened() {
  treeRef.value?.setCheckedKeys(pendingKeys.value)
}

async function onSave() {
  if (!form.name.trim()) return ElMessage.warning('请输入角色名称')
  if (isCreate.value && !form.code.trim()) return ElMessage.warning('请输入角色编码')
  // 已勾选 + 半选（父节点）一起提交
  const checked: number[] = treeRef.value?.getCheckedKeys() || []
  const half: number[] = treeRef.value?.getHalfCheckedKeys() || []
  const menu_ids = [...new Set([...checked, ...half])]
  saving.value = true
  try {
    if (isCreate.value) {
      await createRole({
        name: form.name.trim(),
        code: form.code.trim(),
        description: form.description,
        menu_ids,
      })
      ElMessage.success('角色已创建')
    } else {
      await updateRole(editId.value, {
        name: form.name.trim(),
        description: form.description,
        enabled: form.enabled,
        menu_ids,
      })
      ElMessage.success('角色已更新')
    }
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function onToggleEnabled(row: any) {
  try {
    await updateRole(row.id, { enabled: row.enabled })
    ElMessage.success(row.enabled ? '已启用' : '已禁用')
  } catch {
    row.enabled = !row.enabled
  }
}

async function onDelete(row: any) {
  const ok = await ElMessageBox.confirm(`确认删除角色「${row.name}」？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).then(() => true).catch(() => false)
  if (!ok) return
  await deleteRole(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(() => {
  load()
  loadMenus()
})
</script>

<style scoped>
.toolbar { margin-bottom: 14px; }
.tree-box {
  width: 100%;
  max-height: 320px;
  overflow: auto;
  border: 1px solid #e4e7ed;
  border-radius: 4px;
  padding: 6px;
}
</style>
