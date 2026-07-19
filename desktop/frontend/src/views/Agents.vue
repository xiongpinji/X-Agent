<template>
  <div class="agents-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Agent管理</span>
          <el-button type="primary" @click="createNewAgent">
            <i class="el-icon-plus"></i> 新建Agent
          </el-button>
        </div>
      </template>

      <el-table :data="agents" stripe loading>
        <el-table-column prop="id" label="ID" width="150"></el-table-column>
        <el-table-column prop="name" label="名称"></el-table-column>
        <el-table-column prop="status" label="状态">
          <template #default="{ row }">
            <el-tag :type="row.status === 'running' ? 'success' : 'info'">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180"></el-table-column>
        <el-table-column label="操作" width="200">
          <template #default="{ row }">
            <el-button
              type="primary"
              size="small"
              @click="startAgent(row.id)"
              v-if="row.status !== 'running'"
            >
              启动
            </el-button>
            <el-button
              type="warning"
              size="small"
              @click="stopAgent(row.id)"
              v-else
            >
              停止
            </el-button>
            <el-button type="danger" size="small" @click="deleteAgent(row.id)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { invoke } from '@tauri-apps/api/tauri'
import { ElMessage, ElMessageBox } from 'element-plus'

const agents = ref([])

onMounted(async () => {
  await loadAgents()
})

const loadAgents = async () => {
  try {
    const result = await invoke('list_agents')
    agents.value = result
  } catch (e) {
    ElMessage.error('加载Agent列表失败')
    console.error(e)
  }
}

const createNewAgent = () => {
  ElMessage.info('创建Agent功能开发中...')
}

const startAgent = async (agentId: string) => {
  try {
    await invoke('start_agent', { agentId })
    ElMessage.success('Agent已启动')
    await loadAgents()
  } catch (e) {
    ElMessage.error('启动Agent失败')
    console.error(e)
  }
}

const stopAgent = async (agentId: string) => {
  try {
    await invoke('stop_agent', { agentId })
    ElMessage.success('Agent已停止')
    await loadAgents()
  } catch (e) {
    ElMessage.error('停止Agent失败')
    console.error(e)
  }
}

const deleteAgent = async (agentId: string) => {
  try {
    await ElMessageBox.confirm('确定删除该Agent吗?', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    ElMessage.success('Agent已删除')
    await loadAgents()
  } catch (e) {
    console.error(e)
  }
}
</script>

<style scoped lang="scss">
.agents-page {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
}
</style>
