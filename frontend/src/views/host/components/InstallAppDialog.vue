<template>
  <el-dialog
    :model-value="modelValue"
    title="安装 App"
    width="560px"
    @update:model-value="emit('update:modelValue', $event)"
    @closed="onClosed"
  >
    <el-alert
      type="info"
      :closable="false"
      style="margin-bottom: 12px"
      :title="`目标主机：${host?.hostname || ''}（${host?.ip || ''}）`"
      description="从插件工程选择已安装的插件包（collection/role），将在该主机上以 Ansible playbook 执行安装。任务在后台运行，可到任务管理页查看实时日志。"
    />
    <el-form label-width="90px">
      <el-form-item label="插件" required>
        <el-select
          v-model="pluginId"
          placeholder="选择已安装的插件"
          style="width: 100%"
          @change="onPluginChange"
        >
          <el-option
            v-for="p in plugins"
            :key="p.id"
            :value="p.id"
            :label="`${p.name}（${p.plugin_type}：${p.source}${p.version ? '@' + p.version : ''}）`"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="附加变量">
        <el-input
          v-model="varsText"
          type="textarea"
          :rows="6"
          placeholder='JSON 格式，如 {"key": "value"}；留空则使用插件默认配置'
        />
        <div class="tip">这些变量会以 vars 形式传给合成的 playbook，可被 role 直接读取。</div>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:modelValue', false)">取 消</el-button>
      <el-button type="primary" :loading="loading" @click="onSubmit">开始安装</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { listInstalledPlugins, installApp } from '@/api/modules'

const props = defineProps<{ modelValue: boolean; host: any }>()
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void
  (e: 'installed', taskId: number): void
}>()

const plugins = ref<any[]>([])
const pluginId = ref<number>()
const varsText = ref('')
const loading = ref(false)

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) return
    pluginId.value = undefined
    varsText.value = ''
    try {
      const resp = await listInstalledPlugins()
      plugins.value = (resp.data as any[]) || []
      if (!plugins.value.length) {
        ElMessage.warning('插件工程里没有已安装的插件，请先到「插件工程」安装一个')
      }
    } catch { /* 拦截器已提示 */ }
  },
)

function onPluginChange(id: number) {
  const p = plugins.value.find((x) => x.id === id)
  if (p?.config && Object.keys(p.config).length) {
    varsText.value = JSON.stringify(p.config, null, 2)
  }
}

function onClosed() {
  pluginId.value = undefined
  varsText.value = ''
}

async function onSubmit() {
  if (!props.host?.id) return ElMessage.warning('缺少目标主机')
  if (!pluginId.value) return ElMessage.warning('请选择插件')
  let extraVars: any = {}
  if (varsText.value.trim()) {
    try {
      extraVars = JSON.parse(varsText.value)
    } catch {
      return ElMessage.error('附加变量不是合法的 JSON')
    }
  }
  loading.value = true
  try {
    const resp = await installApp({ host_id: props.host.id, plugin_id: pluginId.value, extra_vars: extraVars })
    const d = resp.data as any
    ElMessage.success('安装任务已提交，可到任务管理页查看进度')
    emit('update:modelValue', false)
    emit('installed', d.last_task_id)
  } catch { /* 拦截器已提示 */ } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.tip { font-size: 12px; color: #909399; line-height: 1.5; margin-top: 4px; }
</style>
