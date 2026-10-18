<template>
  <el-card shadow="never">
    <div class="toolbar">
      <el-button v-permission="'user:create'" type="primary" @click="openCreate">新增用户</el-button>
    </div>

    <el-table v-loading="loading" :data="rows" border stripe>
      <el-table-column prop="username" label="用户名" min-width="120" />
      <el-table-column prop="nickname" label="昵称" min-width="120" />
      <el-table-column label="角色" min-width="180">
        <template #default="{ row }">
          <template v-if="row.roles && row.roles.length">
            <el-tag v-for="r in row.roles" :key="r" size="small" class="tag-gap">{{ r }}</el-tag>
          </template>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="最后登录" min-width="170">
        <template #default="{ row }">{{ fmtTime(row.last_login_at) }}</template>
      </el-table-column>
      <el-table-column label="启用" width="80" align="center">
        <template #default="{ row }">
          <el-switch
            v-model="row.is_active"
            :disabled="row.is_superuser"
            @change="onToggleActive(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button v-permission="'user:update'" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button
            v-permission="'user:delete'"
            link
            type="danger"
            :disabled="row.is_superuser"
            @click="onDelete(row)"
          >删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-pagination
      class="pager"
      background
      layout="total, sizes, prev, pager, next"
      :total="total"
      :current-page="page"
      :page-size="pageSize"
      :page-sizes="[10, 20, 50]"
      @current-change="onPage"
      @size-change="onSize"
    />

    <el-dialog v-model="dialogVisible" :title="isCreate ? '新增用户' : '编辑用户'" width="520px" destroy-on-close>
      <el-form :model="form" label-width="90px">
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" :disabled="!isCreate" placeholder="登录用户名" />
        </el-form-item>
        <el-form-item label="昵称">
          <el-input v-model="form.nickname" placeholder="显示昵称" />
        </el-form-item>
        <el-form-item v-if="!isCreate" label="邮箱">
          <el-input v-model="form.email" placeholder="user@example.com" />
        </el-form-item>
        <el-form-item v-if="!isCreate" label="手机号">
          <el-input v-model="form.phone" placeholder="手机号" />
        </el-form-item>
        <el-form-item v-if="!isCreate" label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item :label="isCreate ? '密码' : '新密码'" :required="isCreate">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="isCreate ? '至少 6 位' : '留空则不修改密码'"
          />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role_ids" multiple placeholder="选择角色（可多选）" style="width: 100%">
            <el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id" />
          </el-select>
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
import { createUser, deleteUser, listRoles, listUsers, updateUser } from '@/api/modules'

const loading = ref(false)
const saving = ref(false)
const rows = ref<any[]>([])
const roles = ref<any[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const dialogVisible = ref(false)
const isCreate = ref(true)
const editId = ref(0)
const form = reactive<any>({
  username: '',
  nickname: '',
  email: '',
  phone: '',
  is_active: true,
  password: '',
  role_ids: [] as number[],
})

function fmtTime(v?: string) {
  if (!v) return '-'
  return String(v).replace('T', ' ').slice(0, 19)
}

async function load() {
  loading.value = true
  try {
    const resp = await listUsers({ page: page.value, page_size: pageSize.value })
    const data = resp.data as any
    rows.value = data.items || []
    total.value = data.total || 0
  } finally {
    loading.value = false
  }
}

async function loadRoles() {
  const resp = await listRoles()
  roles.value = (resp.data as any[]) || []
}

function onPage(p: number) {
  page.value = p
  load()
}

function onSize(s: number) {
  pageSize.value = s
  page.value = 1
  load()
}

function openCreate() {
  isCreate.value = true
  Object.assign(form, {
    username: '', nickname: '', email: '', phone: '',
    is_active: true, password: '', role_ids: [],
  })
  dialogVisible.value = true
}

function openEdit(row: any) {
  isCreate.value = false
  editId.value = row.id
  Object.assign(form, {
    username: row.username,
    nickname: row.nickname || '',
    email: row.email || '',
    phone: row.phone || '',
    is_active: !!row.is_active,
    password: '',
    role_ids: [...(row.role_ids || [])],
  })
  dialogVisible.value = true
}

async function onSave() {
  if (isCreate.value) {
    if (!form.username.trim()) return ElMessage.warning('请输入用户名')
    if (!form.password || form.password.length < 6) return ElMessage.warning('密码至少 6 位')
    saving.value = true
    try {
      await createUser({
        username: form.username.trim(),
        nickname: form.nickname,
        password: form.password,
        email: form.email || null,
        phone: form.phone || '',
        role_ids: form.role_ids,
      })
      ElMessage.success('用户已创建')
      dialogVisible.value = false
      load()
    } finally {
      saving.value = false
    }
  } else {
    saving.value = true
    try {
      const payload: any = {
        nickname: form.nickname,
        email: form.email || null,
        phone: form.phone || '',
        is_active: form.is_active,
        role_ids: form.role_ids,
      }
      if (form.password) payload.password = form.password
      await updateUser(editId.value, payload)
      ElMessage.success('用户已更新')
      dialogVisible.value = false
      load()
    } finally {
      saving.value = false
    }
  }
}

async function onToggleActive(row: any) {
  try {
    await updateUser(row.id, { is_active: row.is_active })
    ElMessage.success(row.is_active ? '已启用' : '已禁用')
  } catch {
    row.is_active = !row.is_active
  }
}

async function onDelete(row: any) {
  const ok = await ElMessageBox.confirm(`确认删除用户「${row.username}」？`, '删除确认', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  }).then(() => true).catch(() => false)
  if (!ok) return
  await deleteUser(row.id)
  ElMessage.success('已删除')
  load()
}

onMounted(() => {
  load()
  loadRoles()
})
</script>

<style scoped>
.toolbar { margin-bottom: 14px; }
.pager { margin-top: 14px; justify-content: flex-end; }
.tag-gap { margin-right: 4px; }
</style>
