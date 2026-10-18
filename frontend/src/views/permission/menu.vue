<template>
  <el-card shadow="never">
    <div class="toolbar">
      <el-button v-permission="'menu:create'" type="primary" @click="openCreate">新增菜单</el-button>
    </div>

    <el-table
      v-loading="loading"
      :data="menus"
      row-key="id"
      :tree-props="{ children: 'children' }"
      default-expand-all
      border
    >
      <el-table-column prop="name" label="名称" min-width="180" />
      <el-table-column prop="path" label="路由地址" min-width="140">
        <template #default="{ row }">{{ row.path || '-' }}</template>
      </el-table-column>
      <el-table-column prop="component" label="组件" min-width="150">
        <template #default="{ row }">{{ row.component || '-' }}</template>
      </el-table-column>
      <el-table-column prop="icon" label="图标" width="90">
        <template #default="{ row }">{{ row.icon || '-' }}</template>
      </el-table-column>
      <el-table-column prop="sort" label="排序" width="70" align="center" />
      <el-table-column label="类型" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="typeTag(row.menu_type).type" size="small">{{ typeTag(row.menu_type).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="permission" label="权限标识" min-width="130">
        <template #default="{ row }">{{ row.permission || '-' }}</template>
      </el-table-column>
      <el-table-column label="可见" width="80" align="center">
        <template #default="{ row }">
          <el-tag :type="row.visible === false ? 'info' : 'success'" size="small">
            {{ row.visible === false ? '隐藏' : '显示' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'menu:update'" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-permission="'menu:delete'" link type="danger" @click="onDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="isCreate ? '新增菜单' : '编辑菜单'" width="560px" destroy-on-close>
      <el-form :model="form" label-width="90px">
        <el-form-item label="上级菜单">
          <el-tree-select
            v-model="form.parent_id"
            :data="parentOptions"
            node-key="id"
            :props="{ label: 'name' }"
            check-strictly
            clearable
            default-expand-all
            placeholder="不选则为顶级菜单"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="菜单 / 按钮 名称" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.menu_type">
            <el-radio value="dir">目录</el-radio>
            <el-radio value="menu">页面</el-radio>
            <el-radio value="button">按钮</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.menu_type !== 'button'" label="路由地址">
          <el-input v-model="form.path" placeholder="如 /host/list" />
        </el-form-item>
        <el-form-item v-if="form.menu_type === 'menu'" label="组件路径">
          <el-input v-model="form.component" placeholder="views 下路径，如 host/list/index" />
        </el-form-item>
        <el-form-item v-if="form.menu_type !== 'button'" label="图标">
          <el-input v-model="form.icon" placeholder="Element Plus 图标名，如 Monitor" />
        </el-form-item>
        <el-form-item v-if="form.menu_type !== 'button'" label="排序">
          <el-input-number v-model="form.sort" :min="0" :max="999" />
        </el-form-item>
        <el-form-item v-if="form.menu_type === 'button'" label="权限标识" required>
          <el-input v-model="form.permission" placeholder="如 host:create" />
        </el-form-item>
        <el-form-item v-if="form.menu_type !== 'button'" label="是否可见">
          <el-switch v-model="form.visible" />
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
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createMenu, deleteMenu, menuTree, updateMenu } from '@/api/modules'

const loading = ref(false)
const saving = ref(false)
const menus = ref<any[]>([])

const dialogVisible = ref(false)
const isCreate = ref(true)
const editId = ref(0)
const form = reactive<any>({
  parent_id: null as number | null,
  name: '',
  path: '',
  component: '',
  icon: '',
  sort: 0,
  menu_type: 'menu',
  permission: '',
  visible: true,
})

const TYPE_MAP: Record<string, { label: string; type: string }> = {
  dir: { label: '目录', type: 'warning' },
  menu: { label: '页面', type: 'success' },
  button: { label: '按钮', type: 'info' },
}

function typeTag(t: string) {
  return TYPE_MAP[t] || { label: t || '-', type: 'info' }
}

async function load() {
  loading.value = true
  try {
    const resp = await menuTree()
    menus.value = (resp.data as any[]) || []
  } finally {
    loading.value = false
  }
}

/** 编辑时：父级选项排除自身及其子孙节点，避免循环挂载 */
const parentOptions = computed(() => {
  const filterSelf = (nodes: any[], excludeId: number): any[] =>
    nodes
      .filter((n) => n.id !== excludeId)
      .map((n) => ({ ...n, children: n.children && n.children.length ? filterSelf(n.children, excludeId) : [] }))
  if (isCreate.value) return menus.value
  return filterSelf(menus.value, editId.value)
})

function openCreate() {
  isCreate.value = true
  Object.assign(form, {
    parent_id: null, name: '', path: '', component: '', icon: '',
    sort: 0, menu_type: 'menu', permission: '', visible: true,
  })
  dialogVisible.value = true
}

function openEdit(row: any) {
  isCreate.value = false
  editId.value = row.id
  Object.assign(form, {
    parent_id: row.parent_id ?? null,
    name: row.name || '',
    path: row.path || '',
    component: row.component || '',
    icon: row.icon || '',
    sort: row.sort ?? 0,
    menu_type: row.menu_type || 'menu',
    permission: row.permission || '',
    visible: row.visible !== false,
  })
  dialogVisible.value = true
}

async function onSave() {
  if (!form.name.trim()) return ElMessage.warning('请输入名称')
  if (form.menu_type === 'button' && !form.permission.trim()) return ElMessage.warning('请输入权限标识')
  if (form.menu_type === 'menu' && !form.path.trim()) return ElMessage.warning('请输入路由地址')
  if (editId.value && form.parent_id === editId.value) return ElMessage.warning('上级菜单不能选择自己')
  saving.value = true
  try {
    const payload: any = {
      parent_id: form.parent_id || null,
      name: form.name.trim(),
      menu_type: form.menu_type,
      permission: form.menu_type === 'button' ? form.permission.trim() : form.permission || null,
      path: form.menu_type === 'button' ? '' : form.path.trim(),
      component: form.menu_type === 'menu' ? form.component.trim() : '',
      icon: form.menu_type === 'button' ? '' : form.icon.trim(),
      sort: Number(form.sort) || 0,
      visible: form.menu_type === 'button' ? true : form.visible,
    }
    if (isCreate.value) {
      await createMenu(payload)
      ElMessage.success('菜单已创建')
    } else {
      await updateMenu(editId.value, payload)
      ElMessage.success('菜单已更新')
    }
    dialogVisible.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function onDelete(row: any) {
  const ok = await ElMessageBox.confirm(`确认删除菜单「${row.name}」？删除后不可恢复`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).then(() => true).catch(() => false)
  if (!ok) return
  await deleteMenu(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(load)
</script>

<style scoped>
.toolbar { margin-bottom: 14px; }
</style>
