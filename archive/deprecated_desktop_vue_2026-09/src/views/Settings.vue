<template>
  <div class="settings-page">
    <el-row :gutter="20">
      <el-col :xs="24" :md="6">
        <div class="settings-menu">
          <div
            v-for="item in menuItems"
            :key="item.key"
            class="menu-item"
            :class="{ active: activeTab === item.key }"
            @click="activeTab = item.key"
          >
            <i :class="item.icon"></i>
            <span>{{ item.label }}</span>
          </div>
        </div>
      </el-col>

      <el-col :xs="24" :md="18">
        <el-card>
          <!-- 基本设置 -->
          <template v-if="activeTab === 'basic'">
            <template #header>
              <div class="card-header">基本设置</div>
            </template>
            <el-form :model="settings" label-width="120px">
              <el-form-item label="后端地址">
                <el-input v-model="settings.backend_url" placeholder="http://localhost" />
              </el-form-item>
              <el-form-item label="后端端口">
                <el-input-number v-model="settings.backend_port" :min="1" :max="65535" />
              </el-form-item>
              <el-form-item label="语言">
                <el-select v-model="settings.language">
                  <el-option label="中文" value="zh-CN"></el-option>
                  <el-option label="English" value="en-US"></el-option>
                </el-select>
              </el-form-item>
              <el-form-item label="主题">
                <el-select v-model="settings.theme">
                  <el-option label="自动" value="auto"></el-option>
                  <el-option label="浅色" value="light"></el-option>
                  <el-option label="深色" value="dark"></el-option>
                </el-select>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="saveSettings">保存设置</el-button>
              </el-form-item>
            </el-form>
          </template>

          <!-- 高级设置 -->
          <template v-if="activeTab === 'advanced'">
            <template #header>
              <div class="card-header">高级设置</div>
            </template>
            <el-form :model="settings" label-width="120px">
              <el-form-item label="日志级别">
                <el-select v-model="settings.log_level">
                  <el-option label="Debug" value="debug"></el-option>
                  <el-option label="Info" value="info"></el-option>
                  <el-option label="Warn" value="warn"></el-option>
                  <el-option label="Error" value="error"></el-option>
                </el-select>
              </el-form-item>
              <el-form-item label="自动更新">
                <el-switch v-model="settings.auto_update"></el-switch>
              </el-form-item>
              <el-form-item label="离线模式">
                <el-switch v-model="settings.offline_mode"></el-switch>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="saveSettings">保存设置</el-button>
              </el-form-item>
            </el-form>
          </template>

          <!-- 关于 -->
          <template v-if="activeTab === 'about'">
            <template #header>
              <div class="card-header">关于</div>
            </template>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="应用名称">X-Agent Desktop</el-descriptions-item>
              <el-descriptions-item label="版本">0.1.0</el-descriptions-item>
              <el-descriptions-item label="构建日期">2026-05-28</el-descriptions-item>
              <el-descriptions-item label="官方网站">
                <el-link href="https://x-agent.com" target="_blank">https://x-agent.com</el-link>
              </el-descriptions-item>
              <el-descriptions-item label="许可证">MIT</el-descriptions-item>
            </el-descriptions>
            <div style="margin-top: 20px">
              <el-button @click="checkUpdate">检查更新</el-button>
              <el-button @click="openLogs">查看日志</el-button>
            </div>
          </template>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { invoke } from '@tauri-apps/api/tauri'
import { ElMessage } from 'element-plus'

const activeTab = ref('basic')
const settings = ref({
  backend_url: 'http://localhost',
  backend_port: 8000,
  language: 'zh-CN',
  theme: 'auto',
  log_level: 'info',
  auto_update: true,
  offline_mode: false
})

const menuItems = [
  { key: 'basic', label: '基本设置', icon: 'el-icon-setting' },
  { key: 'advanced', label: '高级设置', icon: 'el-icon-tools' },
  { key: 'about', label: '关于', icon: 'el-icon-info' }
]

onMounted(async () => {
  await loadSettings()
})

const loadSettings = async () => {
  try {
    const result = await invoke('get_settings')
    settings.value = result
  } catch (e) {
    ElMessage.error('加载设置失败')
    console.error(e)
  }
}

const saveSettings = async () => {
  try {
    await invoke('update_settings', { settings: settings.value })
    ElMessage.success('设置已保存')
  } catch (e) {
    ElMessage.error('保存设置失败')
    console.error(e)
  }
}

const checkUpdate = () => {
  ElMessage.info('检查更新功能开发中...')
}

const openLogs = () => {
  ElMessage.info('查看日志功能开发中...')
}
</script>

<style scoped lang="scss">
.settings-page {
  .settings-menu {
    display: flex;
    flex-direction: column;
    gap: 10px;

    .menu-item {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 12px 16px;
      border-radius: 4px;
      cursor: pointer;
      transition: all 0.3s;
      background: var(--el-fill-color-light);

      &:hover {
        background: var(--el-fill-color);
      }

      &.active {
        background: var(--el-color-primary-light-7);
        color: var(--el-color-primary);
      }
    }
  }

  .card-header {
    font-weight: bold;
    font-size: 16px;
  }
}
</style>
