<template>
  <div class="dashboard-page">
    <!-- 统计卡片 -->
    <el-row :gutter="16" class="stat-row">
      <el-col :xs="12" :sm="12" :md="6">
        <div class="stat-card">
          <div class="stat-icon icon-total"><el-icon :size="26"><Platform /></el-icon></div>
          <div class="stat-body">
            <div class="stat-value">{{ overview.total ?? 0 }}</div>
            <div class="stat-label">主机总数</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <div class="stat-card">
          <div class="stat-icon icon-online"><el-icon :size="26"><Connection /></el-icon></div>
          <div class="stat-body">
            <div class="stat-value text-success">{{ overview.online ?? 0 }}</div>
            <div class="stat-label">在线主机</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <div class="stat-card">
          <div class="stat-icon icon-offline"><el-icon :size="26"><CircleClose /></el-icon></div>
          <div class="stat-body">
            <div class="stat-value text-danger">{{ overview.offline ?? 0 }}</div>
            <div class="stat-label">离线主机</div>
          </div>
        </div>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <div class="stat-card">
          <div class="stat-icon icon-cpu"><el-icon :size="26"><Cpu /></el-icon></div>
          <div class="stat-body">
            <div class="stat-value text-warning">
              {{ overview.avg && overview.avg.cpu_usage != null ? overview.avg.cpu_usage + '%' : '-' }}
            </div>
            <div class="stat-label">平均 CPU 使用率</div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 图表区 -->
    <el-row :gutter="16" class="chart-row">
      <el-col :xs="24" :md="8">
        <el-card shadow="never" header="主机状态分布">
          <div ref="statusChartRef" class="chart"></div>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="16">
        <el-card shadow="never" header="CPU 使用率 Top 10">
          <div ref="topChartRef" class="chart"></div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 主机列表 -->
    <el-card shadow="never" class="table-card">
      <template #header>
        <div class="card-header">
          <span>主机列表</span>
          <el-button size="small" :icon="Refresh" circle title="刷新" @click="loadOverview" />
        </div>
      </template>
      <el-table v-loading="loading" :data="pagedHosts" row-class-name="clickable-row" @row-click="openHost">
        <el-table-column prop="hostname" label="主机名" min-width="130" show-overflow-tooltip />
        <el-table-column prop="ip" label="IP 地址" min-width="130" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="statusTag(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="CPU 使用率" min-width="170">
          <template #default="{ row }">
            <el-progress v-if="row.cpu_usage != null" :percentage="clampPct(row.cpu_usage)" :stroke-width="8" :color="pctColor" />
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="内存使用率" min-width="170">
          <template #default="{ row }">
            <el-progress v-if="row.mem_used_pct != null" :percentage="clampPct(row.mem_used_pct)" :stroke-width="8" :color="pctColor" />
            <span v-else class="muted">-</span>
          </template>
        </el-table-column>
        <el-table-column label="最近采集时间" min-width="170">
          <template #default="{ row }">{{ fmtTime(row.last_collect_at) }}</template>
        </el-table-column>
        <el-table-column label="" width="60">
          <template #default>
            <el-icon class="row-arrow"><ArrowRight /></el-icon>
          </template>
        </el-table-column>
      </el-table>
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        class="pager"
        :total="(overview.hosts || []).length"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
      />
    </el-card>

    <!-- 单机详情抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      size="740px"
      :title="`主机详情 · ${currentHost?.hostname || ''}`"
      @opened="initDetailCharts"
      @closed="disposeDetailCharts"
    >
      <div v-loading="detailLoading" class="detail-body">
        <el-descriptions title="当前快照" :column="3" size="small" border>
          <el-descriptions-item label="CPU 使用率">{{ fmtPct(current?.cpu_usage) }}</el-descriptions-item>
          <el-descriptions-item label="内存使用率">{{ fmtPct(current?.mem_used_pct) }}</el-descriptions-item>
          <el-descriptions-item label="负载 (1m)">{{ current?.load1 ?? '-' }}</el-descriptions-item>
          <el-descriptions-item label="内存用量">{{ fmtMB(current?.mem_used_mb) }} / {{ fmtMB(current?.mem_total_mb) }}</el-descriptions-item>
          <el-descriptions-item label="根盘使用率">{{ fmtPct(current?.disk_root_used_pct) }}</el-descriptions-item>
          <el-descriptions-item label="网络 ↓ / ↑">{{ fmtKbps(current?.net_rx_kbps) }} / {{ fmtKbps(current?.net_tx_kbps) }}</el-descriptions-item>
          <el-descriptions-item label="运行时长">{{ fmtUptime(current?.uptime_s) }}</el-descriptions-item>
          <el-descriptions-item label="采集时间" :span="2">{{ fmtTime(current?.collected_at) }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="section-title">磁盘</h4>
        <el-table :data="disks" size="small" border>
          <el-table-column prop="mount" label="挂载点" min-width="110" show-overflow-tooltip />
          <el-table-column prop="device" label="设备" min-width="130" show-overflow-tooltip />
          <el-table-column label="总量" width="100">
            <template #default="{ row }">{{ fmtMB(row.total_mb) }}</template>
          </el-table-column>
          <el-table-column label="已用" width="100">
            <template #default="{ row }">{{ fmtMB(row.used_mb) }}</template>
          </el-table-column>
          <el-table-column label="使用率" width="90" align="center">
            <template #default="{ row }">{{ fmtPct(row.used_pct) }}</template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!detailLoading && !disks.length" description="暂无磁盘数据" :image-size="60" />

        <div class="range-bar">
          <h4 class="section-title" style="margin-bottom: 0">历史趋势</h4>
          <el-radio-group v-model="rangeMinutes" size="small" @change="loadHistory">
            <el-radio-button :value="30">30 分钟</el-radio-button>
            <el-radio-button :value="60">1 小时</el-radio-button>
            <el-radio-button :value="360">6 小时</el-radio-button>
            <el-radio-button :value="1440">24 小时</el-radio-button>
          </el-radio-group>
        </div>
        <div class="chart-title">CPU 使用率</div>
        <div ref="cpuChartRef" class="chart history-chart"></div>
        <div class="chart-title">内存使用率</div>
        <div ref="memChartRef" class="chart history-chart"></div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { ArrowRight, CircleClose, Connection, Cpu, Platform, Refresh } from '@element-plus/icons-vue'
import { dashboardOverview, hostCurrentMetric, hostMetricHistory } from '@/api/modules'

/** 大屏概览数据 */
const overview = ref<any>({ total: 0, online: 0, offline: 0, avg: {}, cpu_top: [], hosts: [] })
const loading = ref(false)

/** 图表实例与容器 */
const statusChartRef = ref<HTMLDivElement>()
const topChartRef = ref<HTMLDivElement>()
const cpuChartRef = ref<HTMLDivElement>()
const memChartRef = ref<HTMLDivElement>()
let statusChart: echarts.ECharts | null = null
let topChart: echarts.ECharts | null = null
let cpuChart: echarts.ECharts | null = null
let memChart: echarts.ECharts | null = null

/** 主机表格（客户端分页） */
const page = ref(1)
const pageSize = ref(10)
const pagedHosts = computed(() => {
  const hosts = overview.value.hosts || []
  const start = (page.value - 1) * pageSize.value
  return hosts.slice(start, start + pageSize.value)
})

/** 详情抽屉 */
const drawerVisible = ref(false)
const detailLoading = ref(false)
const currentHost = ref<any>(null)
const current = ref<any>(null)
const disks = ref<any[]>([])
const rangeMinutes = ref(60)
const cpuPoints = ref<any[]>([])
const memPoints = ref<any[]>([])

let refreshTimer: ReturnType<typeof setInterval> | null = null

// ---------- 概览加载 ----------
async function loadOverview() {
  loading.value = true
  try {
    const resp = await dashboardOverview()
    overview.value = (resp.data as any) || {}
    if (!overview.value.hosts) overview.value.hosts = []
    renderStatusChart()
    renderTopChart()
  } catch {
    /* 错误已由 request 拦截器统一提示 */
  } finally {
    loading.value = false
  }
}

// ---------- 图表渲染 ----------
function renderStatusChart() {
  const counts: Record<string, number> = { online: 0, offline: 0, unknown: 0 }
  for (const h of overview.value.hosts || []) {
    counts[h.status] = (counts[h.status] || 0) + 1
  }
  statusChart?.setOption({
    legend: { bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: ['42%', '66%'],
        center: ['50%', '44%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
        label: { formatter: '{b}\n{c} 台' },
        data: [
          { name: '在线', value: counts.online || 0, itemStyle: { color: '#67c23a' } },
          { name: '离线', value: counts.offline || 0, itemStyle: { color: '#f56c6c' } },
          { name: '未知', value: counts.unknown || 0, itemStyle: { color: '#909399' } },
        ],
      },
    ],
    tooltip: { trigger: 'item', formatter: '{b}: {c} 台 ({d}%)' },
  })
}

function renderTopChart() {
  const top = (overview.value.cpu_top || []).slice(0, 10)
  // 倒序后最大值显示在最上方
  const rows = [...top].reverse()
  topChart?.setOption({
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' }, valueFormatter: (v: any) => `${v}%` },
    grid: { left: 8, right: 40, top: 10, bottom: 4, containLabel: true },
    xAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' }, splitLine: { lineStyle: { type: 'dashed' } } },
    yAxis: { type: 'category', data: rows.map((r: any) => r.hostname), axisLabel: { width: 110, overflow: 'truncate' } },
    series: [
      {
        type: 'bar',
        barMaxWidth: 16,
        data: rows.map((r: any) => r.cpu_usage),
        label: { show: true, position: 'right', formatter: '{c}%' },
        itemStyle: {
          borderRadius: [0, 4, 4, 0],
          color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
            { offset: 0, color: '#79bbff' },
            { offset: 1, color: '#409eff' },
          ]),
        },
      },
    ],
  })
}

/** 历史折线（cpu_usage / mem_used_pct 均为百分比） */
function lineOption(points: any[], color: string) {
  return {
    tooltip: { trigger: 'axis', valueFormatter: (v: any) => `${v}%` },
    grid: { left: 8, right: 16, top: 24, bottom: 4, containLabel: true },
    xAxis: { type: 'category', boundaryGap: false, data: points.map((p: any) => p.time) },
    yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%' } },
    series: [
      {
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: points.map((p: any) => p.avg),
        lineStyle: { width: 2, color },
        itemStyle: { color },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: color + '55' },
            { offset: 1, color: color + '05' },
          ]),
        },
      },
    ],
  }
}

function renderHistoryCharts() {
  cpuChart?.setOption(lineOption(cpuPoints.value, '#409eff'), true)
  memChart?.setOption(lineOption(memPoints.value, '#67c23a'), true)
}

function handleResize() {
  statusChart?.resize()
  topChart?.resize()
  cpuChart?.resize()
  memChart?.resize()
}

// ---------- 单机详情 ----------
function openHost(row: any) {
  currentHost.value = row
  current.value = null
  disks.value = []
  drawerVisible.value = true
  loadCurrent()
  loadHistory()
}

async function loadCurrent() {
  if (!currentHost.value) return
  detailLoading.value = true
  try {
    const resp = await hostCurrentMetric(currentHost.value.host_id)
    current.value = (resp.data as any) || null
    disks.value = current.value?.disks || []
  } catch {
    /* 拦截器已提示 */
  } finally {
    detailLoading.value = false
  }
}

async function loadHistory() {
  if (!currentHost.value) return
  const minutes = rangeMinutes.value
  const points = minutes <= 60 ? 60 : minutes <= 360 ? 120 : 288
  const hostId = currentHost.value.host_id
  try {
    const [cpuResp, memResp] = await Promise.all([
      hostMetricHistory(hostId, { metric: 'cpu_usage', minutes, points }),
      hostMetricHistory(hostId, { metric: 'mem_used_pct', minutes, points }),
    ])
    if (currentHost.value?.host_id !== hostId) return // 已切换主机
    cpuPoints.value = (cpuResp.data as any)?.points || []
    memPoints.value = (memResp.data as any)?.points || []
    renderHistoryCharts()
  } catch {
    /* 拦截器已提示 */
  }
}

function initDetailCharts() {
  if (!cpuChart && cpuChartRef.value) cpuChart = echarts.init(cpuChartRef.value)
  if (!memChart && memChartRef.value) memChart = echarts.init(memChartRef.value)
  renderHistoryCharts()
}

function disposeDetailCharts() {
  cpuChart?.dispose()
  memChart?.dispose()
  cpuChart = null
  memChart = null
  cpuPoints.value = []
  memPoints.value = []
  current.value = null
  disks.value = []
  currentHost.value = null
}

// ---------- 展示辅助 ----------
function statusTag(s: string): any {
  return s === 'online' ? 'success' : s === 'offline' ? 'danger' : 'info'
}
function statusText(s: string): string {
  return s === 'online' ? '在线' : s === 'offline' ? '离线' : '未知'
}
function clampPct(v: number): number {
  return Math.min(100, Math.max(0, Math.round(Number(v) || 0)))
}
const pctColor = (p: number) => (p < 60 ? '#409eff' : p < 85 ? '#e6a23c' : '#f56c6c')
function fmtPct(v: any): string {
  return v == null ? '-' : `${Number(v).toFixed(1)}%`
}
function fmtMB(v: any): string {
  return v == null ? '-' : `${Number(v).toFixed(0)} MB`
}
function fmtKbps(v: any): string {
  if (v == null) return '-'
  const n = Number(v)
  if (n >= 1024) return `${(n / 1024).toFixed(1)} Mbps`
  return `${n.toFixed(0)} Kbps`
}
function fmtUptime(v: any): string {
  if (v == null) return '-'
  const s = Number(v)
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d} 天 ${h} 小时`
  if (h > 0) return `${h} 小时 ${m} 分`
  return `${m} 分`
}
function fmtTime(v: any): string {
  if (!v) return '-'
  return String(v).replace('T', ' ').slice(0, 19)
}

// ---------- 生命周期 ----------
onMounted(() => {
  statusChart = echarts.init(statusChartRef.value!)
  topChart = echarts.init(topChartRef.value!)
  window.addEventListener('resize', handleResize)
  loadOverview()
  // 30s 定时刷新概览
  refreshTimer = setInterval(loadOverview, 30000)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  if (refreshTimer) clearInterval(refreshTimer)
  statusChart?.dispose()
  topChart?.dispose()
  statusChart = null
  topChart = null
  disposeDetailCharts()
})
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* 统计卡片 */
.stat-row { margin: 0 !important; }
.stat-card {
  background: #fff;
  border-radius: 8px;
  padding: 18px 20px;
  display: flex;
  align-items: center;
  gap: 14px;
  box-shadow: 0 1px 4px rgba(0, 21, 41, 0.08);
}
.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  flex-shrink: 0;
}
.icon-total { background: linear-gradient(135deg, #4f8bff, #2f6bd8); }
.icon-online { background: linear-gradient(135deg, #79d488, #3fb257); }
.icon-offline { background: linear-gradient(135deg, #f89898, #e25c5c); }
.icon-cpu { background: linear-gradient(135deg, #f7c877, #e6973a); }
.stat-value { font-size: 26px; font-weight: 600; line-height: 1.2; }
.stat-label { color: #909399; font-size: 13px; margin-top: 2px; }
.text-success { color: #67c23a; }
.text-danger { color: #f56c6c; }
.text-warning { color: #e6a23c; }

/* 图表 */
.chart-row { margin: 0 !important; }
.chart { height: 280px; width: 100%; }
.history-chart { height: 200px; width: 100%; }
.chart-title { font-size: 13px; color: #606266; margin: 10px 0 4px; }

/* 表格 */
.card-header { display: flex; align-items: center; justify-content: space-between; }
.pager { margin-top: 14px; justify-content: flex-end; }
.clickable-row { cursor: pointer; }
.row-arrow { color: #c0c4cc; }
.muted { color: #c0c4cc; }

/* 抽屉 */
.detail-body { display: flex; flex-direction: column; }
.section-title { font-size: 14px; font-weight: 600; margin: 16px 0 8px; }
.range-bar { display: flex; align-items: center; justify-content: space-between; margin-top: 12px; }
</style>
