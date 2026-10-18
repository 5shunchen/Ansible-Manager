<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <div class="card-header-left">
          <span class="card-title">文件管理</span>
          <el-select
            v-model="newHostId"
            filterable
            placeholder="选择主机打开文件管理"
            style="width: 240px"
          >
            <el-option v-for="h in hosts" :key="h.id" :value="h.id" :label="`${h.hostname}（${h.ip}）`" />
          </el-select>
          <el-button type="primary" plain :disabled="!newHostId" @click="openTab">打开</el-button>
        </div>
      </div>
    </template>

    <el-tabs v-model="activeTab" type="card" closable @tab-remove="onTabRemove">
      <el-tab-pane v-for="t in tabs" :key="t.key" :label="tabLabel(t)" :name="t.key">
        <!-- 每个标签独立文件浏览 -->
        <div class="tab-toolbar">
          <el-button v-permission="'file:write'" :icon="FolderAdd" size="small" @click="onMkdir(t)">新建文件夹</el-button>
          <el-upload v-permission="'file:write'" class="upload-btn" :show-file-list="false" :http-request="(opt) => onUpload(opt, t)" multiple>
            <el-button :icon="Upload" size="small">上传文件</el-button>
          </el-upload>
          <el-button :icon="Refresh" size="small" :loading="t.loading" @click="loadEntries(t)">刷新</el-button>
        </div>

        <div class="crumbs">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item v-for="c in t.crumbs" :key="c.path">
              <span class="crumb" :class="{ active: c.path === t.currentPath }" @click="go(t, c.path)">{{ c.name }}</span>
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <el-table :data="t.entries" v-loading="t.loading" row-key="path" :row-class-name="rowClass" @row-click="(row) => onRowClick(t, row)">
          <el-table-column label="名称" min-width="260">
            <template #default="{ row }">
              <el-icon class="file-icon" :color="row.is_dir ? '#e6a23c' : '#909399'">
                <Folder v-if="row.is_dir" />
                <Document v-else />
              </el-icon>
              <span class="name" :class="{ dir: row.is_dir }">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="类型" width="100">
            <template #default="{ row }">
              <el-tag :type="row.is_dir ? 'warning' : 'info'" effect="plain">{{ row.is_dir ? '文件夹' : '文件' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="120">
            <template #default="{ row }">{{ row.is_dir ? '-' : fmtSize(row.size) }}</template>
          </el-table-column>
          <el-table-column label="修改时间" width="180">
            <template #default="{ row }">{{ fmtTime(row.mtime) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="230" fixed="right">
            <template #default="{ row }">
              <el-button v-if="!row.is_dir" v-permission="'file:read'" link type="primary" :icon="Download" @click.stop="onDownload(t, row)">下载</el-button>
              <el-button v-permission="'file:write'" link type="primary" @click.stop="onRename(t, row)">重命名</el-button>
              <el-button v-permission="'file:delete'" link type="danger" @click.stop="onDelete(t, row)">删除</el-button>
            </template>
          </el-table-column>
          <template #empty><el-empty description="目录为空" /></template>
        </el-table>
      </el-tab-pane>
    </el-tabs>
    <el-empty v-if="!tabs.length" description="从主机列表点「文件管理」或选择主机打开" />
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Folder, Document, FolderAdd, Upload, Refresh, Download } from '@element-plus/icons-vue'
import {
  listHosts, listHostFiles, uploadHostFile, downloadHostFileUrl,
  mkdirHostFile, renameHostFile, deleteHostFile,
} from '@/api/modules'

interface FileTab {
  key: string
  hostId: number
  hostname: string
  currentPath: string
  entries: any[]
  loading: boolean
  crumbs: { name: string; path: string }[]
}

const STORAGE_KEY = 'am_files_tabs'
const hosts = ref<any[]>([])
const newHostId = ref<number | undefined>(undefined)
const tabs = ref<FileTab[]>([])
const activeTab = ref<string>('')

function tabLabel(t: FileTab) {
  return `${t.hostname}（${t.hostId}）`
}

function buildCrumbs(path: string) {
  const parts = path.split('/').filter(Boolean)
  const list = [{ name: '/', path: '/' }]
  let p = ''
  for (const seg of parts) {
    p += `/${seg}`
    list.push({ name: seg, path: p })
  }
  return list
}

function saveTabs() {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(tabs.value.map((t) => ({ hostId: t.hostId, hostname: t.hostname }))))
  } catch { /* ignore */ }
}

function openTabFor(hostId: number, hostname: string) {
  const key = `host-${hostId}`
  if (tabs.value.some((t) => t.key === key)) {
    activeTab.value = key
    return
  }
  tabs.value.push({
    key, hostId, hostname,
    currentPath: '/', entries: [], loading: false, crumbs: buildCrumbs('/'),
  })
  activeTab.value = key
  saveTabs()
  // 取响应式对象（push 后 tabs.value 里的才是 reactive proxy）
  const tab = tabs.value.find((t) => t.key === key)!
  loadEntries(tab)
}

function openTab() {
  if (!newHostId.value) return
  const h = hosts.value.find((x) => x.id === newHostId.value)
  if (!h) return
  openTabFor(h.id, h.hostname)
}

async function loadEntries(t: FileTab) {
  t.loading = true
  try {
    const resp = await listHostFiles(t.hostId, t.currentPath)
    const list = ((resp.data as any)?.entries || []) as any[]
    list.sort((a, b) => Number(b.is_dir) - Number(a.is_dir) || String(a.name).localeCompare(String(b.name)))
    t.entries = list
    t.crumbs = buildCrumbs(t.currentPath)
  } catch { /* 拦截器已提示 */ } finally {
    t.loading = false
  }
}

function go(t: FileTab, path: string) {
  if (path === t.currentPath) return
  t.currentPath = path
  loadEntries(t)
}

function onRowClick(t: FileTab, row: any) {
  if (row.is_dir) go(t, row.path)
}

function rowClass({ row }: any) {
  return row.is_dir ? 'dir-row' : ''
}

function fmtSize(n: any) {
  const size = Number(n) || 0
  if (size <= 0) return '-'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`
  return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`
}
function fmtTime(t: any) {
  const ts = Number(t)
  if (!ts) return '-'
  const d = new Date(ts * 1000)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`
}

function onDownload(t: FileTab, row: any) {
  const token = localStorage.getItem('token') || ''
  window.open(downloadHostFileUrl(t.hostId, row.path, token))
}

async function onRename(t: FileTab, row: any) {
  let name = ''
  try {
    const res = await ElMessageBox.prompt('请输入新名称', `重命名：${row.name}`, {
      inputValue: row.name, inputValidator: (v: string) => !!v?.trim() || '名称不能为空',
      confirmButtonText: '确定', cancelButtonText: '取消',
    })
    name = ((res as any).value || '').trim()
  } catch { return }
  try {
    const dir = row.path.substring(0, row.path.lastIndexOf('/') + 1)
    await renameHostFile(t.hostId, row.path, dir + name)
    ElMessage.success('重命名成功')
    loadEntries(t)
  } catch { /* 拦截器已提示 */ }
}

async function onMkdir(t: FileTab) {
  let name = ''
  try {
    const res = await ElMessageBox.prompt('请输入文件夹名称', '新建文件夹', {
      inputValidator: (v: string) => !!v?.trim() || '名称不能为空',
      confirmButtonText: '创建', cancelButtonText: '取消',
    })
    name = ((res as any).value || '').trim()
  } catch { return }
  try {
    await mkdirHostFile(t.hostId, t.currentPath, name)
    ElMessage.success('创建成功')
    loadEntries(t)
  } catch { /* 拦截器已提示 */ }
}

async function onDelete(t: FileTab, row: any) {
  try {
    await ElMessageBox.confirm(`确认删除${row.is_dir ? '文件夹' : '文件'}「${row.name}」？删除后不可恢复。`, '删除确认', {
      type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消',
    })
  } catch { return }
  try {
    await deleteHostFile(t.hostId, row.path)
    ElMessage.success('已删除')
    loadEntries(t)
  } catch { /* 拦截器已提示 */ }
}

async function onUpload(opt: any, t: FileTab) {
  try {
    await uploadHostFile(t.hostId, t.currentPath, opt.file)
    ElMessage.success(`上传成功：${opt.file?.name || ''}`)
    loadEntries(t)
  } catch (e) {
    opt.onError?.(e)
  }
}

function onTabRemove(key: string) {
  const idx = tabs.value.findIndex((t) => t.key === key)
  if (idx < 0) return
  tabs.value.splice(idx, 1)
  saveTabs()
}

onMounted(async () => {
  try {
    const resp = await listHosts({ page: 1, page_size: 100 })
    hosts.value = (resp.data as any)?.items || []

    const urlHostId = Number(new URLSearchParams(window.location.search).get('host_id'))
    let restored: Array<{ hostId: number; hostname: string }> = []
    try {
      const raw = sessionStorage.getItem(STORAGE_KEY)
      if (raw) restored = JSON.parse(raw)
    } catch { /* ignore */ }

    const toOpen: Array<{ hostId: number; hostname: string }> = []
    const seen = new Set<number>()
    if (urlHostId && hosts.value.some((h) => h.id === urlHostId)) {
      const h = hosts.value.find((x) => x.id === urlHostId)!
      toOpen.push({ hostId: h.id, hostname: h.hostname })
      seen.add(h.id)
    }
    for (const item of restored) {
      if (!seen.has(item.hostId)) {
        const h = hosts.value.find((x) => x.id === item.hostId)
        toOpen.push({ hostId: item.hostId, hostname: h?.hostname || item.hostname })
        seen.add(item.hostId)
      }
    }
    for (const item of toOpen) openTabFor(item.hostId, item.hostname)
  } catch { /* 拦截器已提示 */ }
})
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-header-left { display: flex; align-items: center; gap: 12px; }
.card-title { font-size: 16px; font-weight: 600; }
.tab-toolbar { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.upload-btn { display: inline-flex; margin: 0; }
.crumbs { margin-bottom: 12px; }
.crumb { cursor: pointer; color: #409eff; }
.crumb.active { color: #606266; cursor: default; font-weight: 600; }
.file-icon { margin-right: 6px; vertical-align: -2px; }
.name.dir { color: #409eff; }
:deep(.dir-row) { cursor: pointer; }
</style>
