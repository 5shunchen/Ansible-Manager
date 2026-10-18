<template>
  <el-container class="layout">
    <el-aside width="220px" class="aside">
      <div class="logo">Ansible Manager</div>
      <el-menu
        :default-active="$route.path"
        router
        background-color="#001529"
        text-color="#c8c8c8"
        active-text-color="#ffffff"
      >
        <template v-for="menu in menuStore.sidebarMenus()" :key="menu.id">
          <!-- 有子菜单：嵌套 -->
          <el-sub-menu v-if="menu.children && menu.children.length" :index="menu.path || `dir-${menu.id}`">
            <template #title>
              <el-icon><component :is="iconOf(menu.icon)" /></el-icon>
              <span>{{ menu.name }}</span>
            </template>
            <el-menu-item v-for="sub in menu.children" :key="sub.id" :index="sub.path">
              {{ sub.name }}
            </el-menu-item>
          </el-sub-menu>
          <!-- 无子菜单：直达 -->
          <el-menu-item v-else-if="menu.path" :index="menu.path">
            <el-icon><component :is="iconOf(menu.icon)" /></el-icon>
            <span>{{ menu.name }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="title">{{ $route.meta.title || '' }}</div>
        <div class="header-right">
          <AgentHostFilter />
          <el-dropdown @command="onCommand">
            <span class="user">
              {{ auth.user?.nickname || auth.user?.username }}
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main class="main">
        <!-- 强制先选 Agent 主机：未选择时不渲染业务页面，避免在错误作用域下误操作 -->
        <el-empty v-if="needScope" class="scope-guard" description="请先在右上角选择一台 Agent 主机">
          <el-button type="primary" @click="router.push('/agenthost')">去新增 Agent 主机</el-button>
        </el-empty>
        <!-- 切换 Agent 主机后重挂载当前页面，所有列表随新作用域重新拉取 -->
        <router-view v-else :key="scopeKey" />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ArrowDown } from '@element-plus/icons-vue'
import * as Icons from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'
import AgentHostFilter from '@/components/AgentHostFilter.vue'
import { useAgentHostStore } from '@/stores/agentHost'
import { useAuthStore } from '@/stores/auth'
import { useMenuStore } from '@/stores/menu'

const auth = useAuthStore()
const menuStore = useMenuStore()
const agentHostStore = useAgentHostStore()
const router = useRouter()

/** 作用域豁免页面：
 *  - /agenthost：作用域来源本身（选 Agent 主机的页面）
 *  - /host/terminal、/host/files：带 host_id 的直连操作页（针对某台主机的终端/文件），
 *    不依赖「当前作用域」Agent 主机，不应被守卫挡住 */
const SCOPE_EXEMPT_PATHS = ['/agenthost', '/apphost', '/host/terminal', '/host/files']

const needScope = computed(
  () => !agentHostStore.currentId && !SCOPE_EXEMPT_PATHS.includes(router.currentRoute.value.path),
)

const scopeKey = computed(() => `scope-${agentHostStore.currentId ?? 0}`)

function iconOf(name: string) {
  return (Icons as any)[name] || Icons.Menu
}

function onCommand(cmd: string) {
  if (cmd === 'logout') {
    auth.logout()
    ElMessage.success('已退出登录')
    router.push('/login')
  }
}
</script>

<style scoped>
.layout { height: 100vh; }
.aside { background: #001529; }
.logo {
  height: 60px;
  line-height: 60px;
  color: #fff;
  font-size: 18px;
  font-weight: 600;
  text-align: center;
  letter-spacing: 1px;
}
.aside :deep(.el-menu) { border-right: none; }
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e8e8e8;
}
.title { font-size: 16px; font-weight: 600; }
.header-right { display: flex; align-items: center; gap: 16px; }
.user { cursor: pointer; display: flex; align-items: center; gap: 4px; }
.main { background: #f5f7fa; overflow: auto; }
.scope-guard { margin-top: 15vh; }
</style>
