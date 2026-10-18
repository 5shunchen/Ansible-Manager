<template>
  <el-card shadow="never" v-loading="loading">
    <template #header>
      <span>系统运行配置（修改后立即生效，保存时仅提交变更项）</span>
    </template>

    <div v-for="g in groups" :key="g.prefix" class="group">
      <el-divider content-position="left">{{ g.title }}</el-divider>
      <el-form label-width="280px" class="cfg-form">
        <el-form-item v-for="c in g.items" :key="c.key" :label="c.key">
          <div class="cfg-item">
            <el-switch v-if="typeof c.value === 'boolean'" v-model="c.value" />
            <el-input-number
              v-else-if="typeof c.value === 'number'"
              v-model="c.value"
              :min="0"
              :step="1"
              step-strictly
              controls-position="right"
            />
            <el-input v-else v-model="c.value" style="max-width: 360px" />
            <div class="desc">{{ c.description || '（暂无说明）' }}</div>
          </div>
        </el-form-item>
      </el-form>
    </div>

    <div class="toolbar">
      <el-button @click="load">重置</el-button>
      <el-button v-permission="'system:config'" type="primary" :loading="saving" @click="onSave">保存</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { listSystemConfigs, updateSystemConfigs } from '@/api/modules'

const loading = ref(false)
const saving = ref(false)
const configs = ref<any[]>([])
const original = ref<Record<string, any>>({})

const GROUP_TITLES: Record<string, string> = {
  collect: '监控采集',
  metric: '指标存储',
  task: '任务执行',
  terminal: 'Web 终端',
}

const groups = computed(() => {
  const map = new Map<string, any[]>()
  for (const c of configs.value) {
    const prefix = c.key.includes('.') ? c.key.split('.')[0] : c.key
    if (!map.has(prefix)) map.set(prefix, [])
    map.get(prefix)!.push(c)
  }
  return [...map.entries()].map(([prefix, items]) => ({
    prefix,
    title: GROUP_TITLES[prefix] || prefix,
    items,
  }))
})

async function load() {
  loading.value = true
  try {
    const resp = await listSystemConfigs()
    configs.value = (resp.data as any[]) || []
    const snap: Record<string, any> = {}
    for (const c of configs.value) snap[c.key] = JSON.stringify(c.value)
    original.value = snap
  } finally {
    loading.value = false
  }
}

async function onSave() {
  const changed: Record<string, any> = {}
  for (const c of configs.value) {
    if (JSON.stringify(c.value) !== original.value[c.key]) changed[c.key] = c.value
  }
  if (!Object.keys(changed).length) return ElMessage.info('没有需要保存的修改')
  saving.value = true
  try {
    await updateSystemConfigs(changed)
    ElMessage.success('配置已保存')
    load()
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.group { margin-bottom: 8px; }
.cfg-form { margin-left: 8px; }
.cfg-item { display: flex; align-items: center; gap: 12px; width: 100%; }
.desc { color: #909399; font-size: 12px; line-height: 1.4; }
.toolbar { margin-top: 18px; padding-left: 12px; }
</style>
