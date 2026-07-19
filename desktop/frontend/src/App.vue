<template>
  <div id="app" class="app-container">
    <el-container class="main-layout">
      <el-header class="app-header">
        <div class="header-content">
          <div class="logo">X-Agent</div>
          <div class="header-actions">
            <el-button
              type="text"
              @click="toggleTheme"
              :icon="isDark ? 'sunny' : 'moon'"
            />
            <el-button
              type="text"
              @click="openSettings"
              icon="setting"
            />
            <el-button
              type="text"
              @click="minimizeWindow"
              icon="minus"
            />
            <el-button
              type="text"
              @click="maximizeWindow"
              icon="crop"
            />
            <el-button
              type="text"
              @click="closeWindow"
              icon="close"
            />
          </div>
        </div>
      </el-header>

      <el-container class="content-layout">
        <el-aside class="sidebar" width="250px">
          <nav class="nav-menu">
            <router-link
              v-for="item in menuItems"
              :key="item.path"
              :to="item.path"
              class="nav-item"
              :class="{ active: $route.path === item.path }"
            >
              <i :class="item.icon"></i>
              <span>{{ item.label }}</span>
            </router-link>
          </nav>
        </el-aside>

        <el-main class="main-content">
          <Suspense>
            <template #default>
              <router-view />
            </template>
            <template #fallback>
              <div class="loading-container">
                <el-icon class="is-loading"><Loading /></el-icon>
              </div>
            </template>
          </Suspense>
        </el-main>
      </el-container>

      <el-footer class="app-footer">
        <div class="status-bar">
          <span class="status-item">
            <i :class="backendConnected ? 'el-icon-success' : 'el-icon-warning'"></i>
            {{ backendConnected ? '已连接' : '离线模式' }}
          </span>
          <span class="status-item">
            <i :class="agentRunning ? 'el-icon-video-play' : 'el-icon-video-pause'"></i>
            {{ agentRunning ? '运行中' : '已停止' }}
          </span>
        </div>
      </el-footer>
    </el-container>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, Suspense } from 'vue'
import { useRouter } from 'vue-router'
import { invoke } from '@tauri-apps/api/tauri'
import { appWindow } from '@tauri-apps/api/window'
import { Loading } from '@element-plus/icons-vue'

const router = useRouter()
const isDark = ref(false)
const backendConnected = ref(false)
const agentRunning = ref(false)

const menuItems = [
  { path: '/', label: '首页', icon: 'el-icon-home' },
  { path: '/agents', label: 'Agent管理', icon: 'el-icon-management' },
  { path: '/files', label: '文件浏览', icon: 'el-icon-folder' },
  { path: '/runs', label: '运行历史', icon: 'el-icon-document' },
  { path: '/settings', label: '设置', icon: 'el-icon-setting' },
]

onMounted(async () => {
  // Check backend status
  try {
    await invoke('get_backend_status')
    backendConnected.value = true
  } catch (e) {
    backendConnected.value = false
  }

  // Load theme preference
  try {
    const theme = await invoke('get_theme')
    isDark.value = theme === 'dark'
  } catch (e) {
    console.error('Failed to load theme:', e)
  }

  // Prefetch non-critical resources
  if ('requestIdleCallback' in window) {
    requestIdleCallback(() => {
      // Preload images and other resources
      const link = document.createElement('link')
      link.rel = 'prefetch'
      link.href = '/api/health'
      document.head.appendChild(link)
    })
  }
})

const toggleTheme = async () => {
  isDark.value = !isDark.value
  const theme = isDark.value ? 'dark' : 'light'
  try {
    await invoke('set_theme', { theme })
    document.documentElement.setAttribute('data-theme', theme)
  } catch (e) {
    console.error('Failed to set theme:', e)
  }
}

const openSettings = () => {
  router.push('/settings')
}

const minimizeWindow = async () => {
  try {
    await invoke('minimize_window')
  } catch (e) {
    console.error('Failed to minimize window:', e)
  }
}

const maximizeWindow = async () => {
  try {
    await invoke('maximize_window')
  } catch (e) {
    console.error('Failed to maximize window:', e)
  }
}

const closeWindow = async () => {
  try {
    await invoke('close_window')
  } catch (e) {
    console.error('Failed to close window:', e)
  }
}
</script>

<style scoped lang="scss">
.app-container {
  width: 100%;
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  color: var(--el-text-color-primary);
}

.main-layout {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.app-header {
  background: var(--el-bg-color-overlay);
  border-bottom: 1px solid var(--el-border-color-light);
  padding: 0 20px;
  display: flex;
  align-items: center;
  height: 60px;
  flex-shrink: 0;

  .header-content {
    width: 100%;
    display: flex;
    justify-content: space-between;
    align-items: center;

    .logo {
      font-size: 20px;
      font-weight: bold;
      color: var(--el-color-primary);
    }

    .header-actions {
      display: flex;
      gap: 10px;
    }
  }
}

.content-layout {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.sidebar {
  background: var(--el-bg-color-overlay);
  border-right: 1px solid var(--el-border-color-light);
  overflow-y: auto;
  flex-shrink: 0;

  .nav-menu {
    padding: 20px 0;

    .nav-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 20px;
      color: var(--el-text-color-primary);
      text-decoration: none;
      transition: all 0.3s;
      will-change: background-color, color;

      &:hover {
        background: var(--el-fill-color-light);
        color: var(--el-color-primary);
      }

      &.active {
        background: var(--el-color-primary-light-7);
        color: var(--el-color-primary);
        border-left: 3px solid var(--el-color-primary);
      }

      i {
        font-size: 16px;
      }
    }
  }
}

.main-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  contain: layout style paint;
}

.loading-container {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  font-size: 24px;
}

.app-footer {
  background: var(--el-bg-color-overlay);
  border-top: 1px solid var(--el-border-color-light);
  padding: 10px 20px;
  height: 40px;
  display: flex;
  align-items: center;
  flex-shrink: 0;

  .status-bar {
    display: flex;
    gap: 20px;
    font-size: 12px;

    .status-item {
      display: flex;
      align-items: center;
      gap: 5px;
    }
  }
}
</style>
