<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <div class="card-header-left">
          <span class="card-title">Web 终端</span>
          <el-select
            v-model="newHostId"
            filterable
            placeholder="选择主机打开终端"
            style="width: 240px"
          >
            <el-option v-for="h in hosts" :key="h.id" :value="h.id" :label="`${h.hostname}（${h.ip}）`" />
          </el-select>
          <el-button type="primary" plain :disabled="!newHostId" @click="openTab">打开终端</el-button>
        </div>
        <el-tag v-if="activeTab" :type="tabStatusType(activeTab)" effect="plain">
          {{ tabStatusText(activeTab) }}
        </el-tag>
      </div>
    </template>

    <el-tabs v-model="activeTab" type="card" closable @tab-remove="onTabRemove" @tab-change="onTabChange">
      <el-tab-pane v-for="t in tabs" :key="t.key" :label="tabLabel(t)" :name="t.key">
        <div :ref="(el) => setTermElRef(t.key, el as HTMLElement)" class="term" />
      </el-tab-pane>
    </el-tabs>
    <el-empty v-if="!tabs.length" description="从主机列表点「Web终端」或选择主机打开终端" />
  </el-card>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Terminal } from 'xterm'
import { FitAddon } from 'xterm-addon-fit'
import 'xterm/css/xterm.css'
import { listHosts } from '@/api/modules'

interface TabSession {
  key: string
  hostId: number
  hostname: string
  ws: WebSocket | null
  term: Terminal | null
  fitAddon: FitAddon | null
  status: 'idle' | 'connecting' | 'open' | 'closed'
}

const STORAGE_KEY = 'am_terminal_tabs'
const hosts = ref<any[]>([])
const newHostId = ref<number | undefined>(undefined)
const tabs = ref<TabSession[]>([])
const activeTab = ref<string>('')
const termEls: Record<string, HTMLElement> = {}

function setTermElRef(key: string, el: HTMLElement) {
  if (el) termEls[key] = el
}
function tabLabel(t: TabSession) {
  return `${t.hostname}（${t.hostId}）`
}
function tabStatusType(t: TabSession | undefined) {
  if (!t) return 'info'
  return t.status === 'open' ? 'success' : t.status === 'connecting' ? 'warning' : 'info'
}
function tabStatusText(t: TabSession | undefined) {
  if (!t) return ''
  return { connecting: '连接中…', open: '已连接', closed: '已断开', idle: '未连接' }[t.status]
}
function activeTabSession() {
  return tabs.value.find((t) => t.key === activeTab.value)
}

function sysWrite(t: TabSession, text: string) {
  t.term?.write(`\r\n\x1b[33m${text}\x1b[0m\r\n`)
}

function connectTab(t: TabSession) {
  if (t.ws) {
    t.ws.onopen = null; t.ws.onmessage = null; t.ws.onerror = null; t.ws.onclose = null
    try { t.ws.close() } catch { /* ignore */ }
    t.ws = null
  }
  t.term?.reset()
  t.status = 'connecting'
  const token = localStorage.getItem('token') || ''
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  const base = String(import.meta.env.BASE_URL || '/').replace(/\/+$/, '')
  const url = `${proto}://${location.host}${base}/api/v1/ws/terminal/${t.hostId}?token=${encodeURIComponent(token)}`
  const sock = new WebSocket(url)
  t.ws = sock
  sock.onopen = () => {
    t.status = 'open'
    fitTab(t)
  }
  sock.onmessage = (ev: MessageEvent) => {
    try {
      const msg = JSON.parse(ev.data)
      if (msg?.type === 'output') t.term?.write(String(msg.data ?? ''))
    } catch { /* ignore */ }
  }
  sock.onclose = (ev: CloseEvent) => {
    t.status = 'closed'
    if (ev.code === 4502) sysWrite(t, 'SSH 连接失败')
  }
}

function fitTab(t: TabSession) {
  if (!t.term || !t.fitAddon) return
  try { t.fitAddon.fit() } catch { /* ignore */ }
  if (t.ws?.readyState === WebSocket.OPEN) {
    t.ws.send(JSON.stringify({ type: 'resize', cols: t.term.cols, rows: t.term.rows }))
  }
}

function saveTabs() {
  const data = tabs.value.map((t) => ({ hostId: t.hostId, hostname: t.hostname }))
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data)) } catch { /* ignore */ }
}

/** 打开一个主机的终端标签（内部统一入口）。 */
function openTabFor(hostId: number, hostname: string) {
  const key = `host-${hostId}`
  if (tabs.value.some((t) => t.key === key)) {
    activeTab.value = key
    return
  }
  const term = new Terminal({
    cursorBlink: true, fontSize: 14, fontFamily: 'Consolas, Menlo, monospace',
    scrollback: 5000, theme: { background: '#1e1e1e' },
  })
  const fitAddon = new FitAddon()
  term.loadAddon(fitAddon)
  term.onData((d) => {
    const t = tabs.value.find((x) => x.key === key)
    if (t?.ws?.readyState === WebSocket.OPEN) t.ws.send(JSON.stringify({ type: 'input', data: d }))
  })
  const tab: TabSession = { key, hostId, hostname, ws: null, term, fitAddon, status: 'idle' }
  tabs.value.push(tab)
  activeTab.value = key
  saveTabs()
  setTimeout(() => {
    const el = termEls[key]
    if (el) { term.open(el); fitAddon.fit() }
    connectTab(tab)
  }, 100)
}

function openTab() {
  if (!newHostId.value) return
  const h = hosts.value.find((x) => x.id === newHostId.value)
  if (!h) return
  openTabFor(h.id, h.hostname)
}

function onTabRemove(key: string) {
  const idx = tabs.value.findIndex((t) => t.key === key)
  if (idx < 0) return
  const t = tabs.value[idx]
  if (t.ws) {
    t.ws.onopen = null; t.ws.onmessage = null; t.ws.onerror = null; t.ws.onclose = null
    try { t.ws.close() } catch { /* ignore */ }
  }
  t.term?.dispose()
  tabs.value.splice(idx, 1)
  saveTabs()
}

function onTabChange(key: string) {
  const t = tabs.value.find((x) => x.key === key)
  if (t) setTimeout(() => fitTab(t), 100)
}

function onWindowResize() {
  if (activeTab.value) {
    const t = tabs.value.find((x) => x.key === activeTab.value)
    if (t) fitTab(t)
  }
}

onMounted(async () => {
  window.addEventListener('resize', onWindowResize)
  try {
    const resp = await listHosts({ page: 1, page_size: 100 })
    hosts.value = (resp.data as any)?.items || []

    // 1) URL 直接带 host_id（从主机列表跳转）
    const urlHostId = Number(new URLSearchParams(window.location.search).get('host_id'))
    // 2) sessionStorage 恢复上次已打开的所有终端标签
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

onUnmounted(() => {
  window.removeEventListener('resize', onWindowResize)
  for (const t of tabs.value) {
    if (t.ws) {
      t.ws.onopen = null; t.ws.onmessage = null; t.ws.onerror = null; t.ws.onclose = null
      try { t.ws.close() } catch { /* ignore */ }
    }
    t.term?.dispose()
  }
  tabs.value = []
})
</script>

<style scoped>
.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-header-left { display: flex; align-items: center; gap: 12px; }
.card-title { font-size: 16px; font-weight: 600; }
.term { height: calc(100vh - 260px); min-height: 400px; background: #1e1e1e; border-radius: 4px; padding: 6px 8px; }
</style>
