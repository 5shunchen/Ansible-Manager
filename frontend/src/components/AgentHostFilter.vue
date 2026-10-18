<template>
  <div class="agent-host-filter">
    <el-icon class="filter-icon"><Cpu /></el-icon>
    <span class="filter-label">Agent 主机</span>
    <el-select
      :model-value="store.currentId"
      class="filter-select"
      :class="{ 'is-required': !store.currentId }"
      filterable
      clearable
      :loading="store.loading"
      placeholder="请选择 Agent 主机"
      @update:model-value="onChange"
      @visible-change="onVisibleChange"
    >
      <el-option
        v-for="h in store.hosts"
        :key="h.id"
        :value="h.id"
        :label="`${h.hostname}（${h.ip}）`"
      >
        <span class="opt-name">{{ h.hostname }}（{{ h.ip }}）</span>
        <el-tag size="small" :type="statusTagType(h.status)" effect="plain">
          {{ statusText(h.status) }}
        </el-tag>
      </el-option>
      <template #empty>
        <div class="opt-empty">暂无 Agent 主机，请先在「Agent主机」菜单新增</div>
      </template>
    </el-select>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { Cpu } from '@element-plus/icons-vue'
import { useAgentHostStore } from '@/stores/agentHost'

const store = useAgentHostStore()

function statusTagType(s: string): 'success' | 'danger' | 'info' {
  if (s === 'online') return 'success'
  if (s === 'offline') return 'danger'
  return 'info'
}
function statusText(s: string) {
  if (s === 'online') return '在线'
  if (s === 'offline') return '离线'
  return '未知'
}

function onChange(id: number | undefined | null) {
  store.select(id ?? undefined)
}

/** 每次展开都刷新一次，避免主机状态/列表过期 */
function onVisibleChange(visible: boolean) {
  if (visible) store.loadHosts()
}

onMounted(() => {
  store.loadHosts()
})
</script>

<style scoped>
.agent-host-filter {
  display: flex;
  align-items: center;
  gap: 8px;
}
.filter-icon {
  color: #909399;
}
.filter-label {
  font-size: 14px;
  color: #606266;
  white-space: nowrap;
}
.filter-select {
  width: 240px;
}
/* 未选择 Agent 主机：业务页面不可用，给出醒目的必选提示 */
.filter-select.is-required :deep(.el-select__wrapper) {
  box-shadow: 0 0 0 1px #e6a23c inset;
}
.opt-name {
  margin-right: 8px;
}
.opt-empty {
  padding: 8px 0;
  color: #909399;
  font-size: 13px;
  text-align: center;
}
</style>
