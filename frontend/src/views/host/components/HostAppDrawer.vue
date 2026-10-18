<template>
  <el-drawer
    :model-value="modelValue"
    :title="`已安装的 App — ${host?.hostname || ''}`"
    size="560px"
    @update:model-value="emit('update:modelValue', $event)"
    @opened="load"
  >
    <el-table :data="apps" v-loading="loading" size="small" empty-text="该主机上还没有安装任何 App">
      <el-table-column prop="plugin_name" label="App" min-width="140">
        <template #default="{ row }">
          <div>{{ row.plugin_name }}</div>
          <div class="sub">{{ row.plugin_type }} · {{ row.plugin_source }}</div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="version" label="版本" width="80" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button
            link
            type="danger"
            size="small"
            :loading="uninstalling[`row-${row.id}`]"
            :disabled="row.status === 'uninstalling' || row.status === 'installing'"
            @click="onUninstall(row)"
          >卸载</el-button>
        </template>
      </el-table-column>
    </el-table>
    <template #footer>
      <el-button @click="load">刷新</el-button>
      <el-button type="primary" @click="emit('update:modelValue', false)">关闭</el-button>
    </template>
  </el-drawer>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listHostApps, uninstallApp } from '@/api/modules'

const props = defineProps<{ modelValue: boolean; host: any }>()
const emit = defineEmits<{ (e: 'update:modelValue', v: boolean): void }>()
const router = useRouter()

const apps = ref<any[]>([])
const loading = ref(false)
const uninstalling = reactive<Record<string, boolean>>({})

function statusText(s: string) {
  return ({
    installed: '已安装', running: '运行中', installing: '安装中', uninstalling: '卸载中',
    failed: '失败', uninstalled: '已卸载', unknown: '未知',
  } as Record<string, string>)[s] || s
}
function statusType(s: string): 'success' | 'primary' | 'warning' | 'danger' | 'info' {
  if (s === 'installed' || s === 'running') return 'success'
  if (s === 'installing' || s === 'uninstalling') return 'warning'
  if (s === 'failed') return 'danger'
  return 'info'
}

async function load() {
  if (!props.host?.id) return
  loading.value = true
  try {
    const resp = await listHostApps(props.host.id)
    apps.value = (resp.data as any[]) || []
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}

async function onUninstall(row: any) {
  try {
    await ElMessageBox.confirm(`确认卸载「${row.plugin_name}」？将在后台拉起卸载任务。`, '卸载确认', {
      type: 'warning', confirmButtonText: '卸载', cancelButtonText: '取消',
    })
  } catch { return }
  uninstalling[`row-${row.id}`] = true
  try {
    await uninstallApp({ host_id: props.host.id, plugin_id: row.plugin_id })
    ElMessage.success('卸载任务已提交，可到任务管理页查看进度')
    emit('update:modelValue', false)
    router.push('/task')
  } catch { /* 拦截器已提示 */ } finally {
    uninstalling[`row-${row.id}`] = false
  }
}
</script>

<style scoped>
.sub { font-size: 12px; color: #909399; }
</style>
