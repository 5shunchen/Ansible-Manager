<template>
  <div class="login-page">
    <el-card class="login-card">
      <h2 class="title">Ansible Manager</h2>
      <p class="subtitle">主机管理 · 监控 · Playbook · 容器部署</p>
      <el-form :model="form" @keyup.enter="onLogin">
        <!-- SSH 主机密码登录 -->
        <template v-if="mode === 'ssh'">
          <el-form-item>
            <el-input v-model="form.host" placeholder="主机 IP" size="large">
              <template #prefix><el-icon><Monitor /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item>
            <el-input v-model="form.port" placeholder="SSH 端口" size="large">
              <template #prefix><el-icon><Connection /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item>
            <el-input v-model="form.username" placeholder="用户名" size="large">
              <template #prefix><el-icon><User /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item>
            <el-input v-model="form.password" type="password" placeholder="主机密码" size="large" show-password>
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </el-form-item>
        </template>

        <!-- 平台账号登录 -->
        <template v-else>
          <el-form-item>
            <el-input v-model="adminForm.username" placeholder="平台用户名" size="large">
              <template #prefix><el-icon><User /></el-icon></template>
            </el-input>
          </el-form-item>
          <el-form-item>
            <el-input v-model="adminForm.password" type="password" placeholder="平台密码" size="large" show-password>
              <template #prefix><el-icon><Lock /></el-icon></template>
            </el-input>
          </el-form-item>
        </template>

        <!-- 连接测试结果 -->
        <el-alert
          v-if="testResult"
          :title="testResult.title"
          :type="testResult.ok ? 'success' : 'error'"
          :description="testResult.desc"
          :closable="false"
          style="margin-bottom: 16px"
        />

        <div class="btn-row">
          <el-button v-if="mode === 'ssh'" size="large" :loading="testing" @click="onTest">连接测试</el-button>
          <el-button type="primary" size="large" style="flex: 1" :loading="loading" @click="onLogin">
            登 录
          </el-button>
        </div>
        <div class="switch-auth">
          <el-link type="info" :underline="false" @click="mode = mode === 'ssh' ? 'admin' : 'ssh'">
            {{ mode === 'ssh' ? '使用平台账号登录' : '使用主机密码登录' }}
          </el-link>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { User, Lock, Monitor, Connection } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import request from '@/api/request'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const mode = ref<'ssh' | 'admin'>('ssh')

const form = reactive({ host: '', port: '22', username: 'root', password: '' })
const adminForm = reactive({ username: 'admin', password: '' })
const loading = ref(false)
const testing = ref(false)
const testResult = ref<{ ok: boolean; title: string; desc: string } | null>(null)

async function onTest() {
  if (!form.host || !form.password) return ElMessage.warning('请输入主机 IP 和密码')
  testing.value = true
  testResult.value = null
  try {
    const resp = await request.post('/auth/ssh-test', {
      host: form.host, port: Number(form.port) || 22, username: form.username, password: form.password,
    })
    const d = resp.data as any
    testResult.value = {
      ok: true,
      title: `连接成功`,
      desc: `${d.os || 'Linux'} ${d.os_release || ''} · ${d.cpu_cores ?? '?'} 核`,
    }
  } catch {
    // request 拦截器已弹出错误信息
    testResult.value = { ok: false, title: '连接失败', desc: '请检查主机 IP、端口、用户名或密码' }
  } finally {
    testing.value = false
  }
}

async function onLogin() {
  // 平台账号登录
  if (mode.value === 'admin') {
    if (!adminForm.username || !adminForm.password) return ElMessage.warning('请输入用户名和密码')
    loading.value = true
    try {
      const resp = await request.post('/auth/login', { username: adminForm.username, password: adminForm.password })
      const { token, user } = resp.data as any
      auth.setAuth(token, user)
      ElMessage.success('登录成功')
      location.href = '/'
    } finally {
      loading.value = false
    }
    return
  }

  // SSH 主机密码登录
  if (!form.host || !form.password) return ElMessage.warning('请输入主机 IP 和密码')
  loading.value = true
  try {
    const resp = await request.post('/auth/ssh-login', {
      host: form.host, port: Number(form.port) || 22, username: form.username, password: form.password,
    })
    const { token, user } = resp.data as any
    auth.setAuth(token, user)
    ElMessage.success('登录成功')
    location.href = '/'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #1c3faa 0%, #0b1f5c 100%);
}
.login-card { width: 400px; padding: 12px; }
.title { text-align: center; margin: 8px 0 4px; }
.subtitle { text-align: center; color: #999; font-size: 12px; margin-bottom: 24px; }
.btn-row { display: flex; gap: 12px; }
.switch-auth { text-align: center; margin-top: 14px; }
</style>
