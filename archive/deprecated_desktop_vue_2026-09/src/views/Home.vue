<template>
  <div class="home-page">
    <el-row :gutter="20">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="stat-card">
          <template #header>
            <div class="card-header">
              <span>运行中的Agent</span>
            </div>
          </template>
          <div class="stat-value">{{ runningAgents }}</div>
          <div class="stat-label">个</div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="stat-card">
          <template #header>
            <div class="card-header">
              <span>总运行次数</span>
            </div>
          </template>
          <div class="stat-value">{{ totalRuns }}</div>
          <div class="stat-label">次</div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="stat-card">
          <template #header>
            <div class="card-header">
              <span>成功率</span>
            </div>
          </template>
          <div class="stat-value">{{ successRate }}%</div>
          <div class="stat-label">成功</div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="stat-card">
          <template #header>
            <div class="card-header">
              <span>后端状态</span>
            </div>
          </template>
          <div class="stat-value" :class="backendStatus ? 'success' : 'error'">
            {{ backendStatus ? '在线' : '离线' }}
          </div>
          <div class="stat-label">{{ backendStatus ? '已连接' : '未连接' }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :xs="24" :md="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>快速操作</span>
            </div>
          </template>
          <div class="quick-actions">
            <el-button type="primary" @click="createAgent">
              <i class="el-icon-plus"></i> 创建Agent
            </el-button>
            <el-button @click="openFileManager">
              <i class="el-icon-folder-opened"></i> 打开文件管理
            </el-button>
            <el-button @click="viewLogs">
              <i class="el-icon-document"></i> 查看日志
            </el-button>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>系统信息</span>
            </div>
          </template>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="应用版本">0.1.0</el-descriptions-item>
            <el-descriptions-item label="后端地址">{{ backendUrl }}</el-descriptions-item>
            <el-descriptions-item label="数据目录">{{ dataDir }}</el-descriptions-item>
            <el-descriptions-item label="离线模式">{{ offlineMode ? '启用' : '禁用' }}</el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="20" style="margin-top: 20px">
      <el-col :xs="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>最近运行</span>
            </div>
          </template>
          <el-table :data="recentRuns" stripe>
            <el-table-column prop="id" label="运行ID" width="150"></el-table-column>
            <el-table-column prop="agent_name" label="Agent名称"></el-table-column>
            <el-table-column prop="status" label="状态">
              <template #default="{ row }">
                <el-tag :type="row.status === 'success' ? 'success' : 'danger'">
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="创建时间" width="180"></el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { invoke } from '@tauri-apps/api/tauri'
import { ElMessage } from 'element-plus'

const runningAgents = ref(0)
const totalRuns = ref(0)
const successRate = ref(0)
const backendStatus = ref(false)
const backendUrl = ref('http://localhost:8000')
const dataDir = ref('~/.xagent/data')
const offlineMode = ref(false)
const recentRuns = ref([])

onMounted(async () => {
  await loadDashboardData()
})

const loadDashboardData = async () => {
  try {
    // Get backend status
    const status = await invoke('get_backend_status')
    backendStatus.value = true
  } catch (e) {
    backendStatus.value = false
  }

  // Get settings
  try {
    const settings = await invoke('get_settings')
    backendUrl.value = `${settings.backend_url}:${settings.backend_port}`
    offlineMode.value = settings.offline_mode
  } catch (e) {
    console.error('Failed to load settings:', e)
  }

  // Mock data for demo
  runningAgents.value = 2
  totalRuns.value = 42
  successRate.value = 95
  recentRuns.value = [
    {
      id: 'run-001',
      agent_name: 'DataProcessor',
      status: 'success',
      created_at: new Date().toLocaleString()
    },
    {
      id: 'run-002',
      agent_name: 'WebScraper',
      status: 'success',
      created_at: new Date().toLocaleString()
    }
  ]
}

const createAgent = () => {
  ElMessage.info('创建Agent功能开发中...')
}

const openFileManager = () => {
  ElMessage.info('打开文件管理器...')
}

const viewLogs = () => {
  ElMessage.info('查看日志功能开发中...')
}
</script>

<style scoped lang="scss">
.home-page {
  .stat-card {
    text-align: center;

    .stat-value {
      font-size: 32px;
      font-weight: bold;
      color: var(--el-color-primary);
      margin: 10px 0;

      &.success {
        color: var(--el-color-success);
      }

      &.error {
        color: var(--el-color-danger);
      }
    }

    .stat-label {
      font-size: 12px;
      color: var(--el-text-color-secondary);
    }
  }

  .quick-actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }
}
</style>
