<template>
  <div class="runs-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>运行历史</span>
          <div class="filters">
            <el-select v-model="filterStatus" placeholder="筛选状态" style="width: 150px">
              <el-option label="全部" value=""></el-option>
              <el-option label="成功" value="success"></el-option>
              <el-option label="失败" value="failed"></el-option>
              <el-option label="运行中" value="running"></el-option>
            </el-select>
            <el-button @click="refreshRuns">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table :data="filteredRuns" stripe>
        <el-table-column prop="id" label="运行ID" width="150"></el-table-column>
        <el-table-column prop="agent_name" label="Agent名称"></el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">
              {{ row.status }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180"></el-table-column>
        <el-table-column prop="duration" label="耗时" width="100"></el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="viewDetails(row)">
              详情
            </el-button>
            <el-button type="danger" size="small" @click="deleteRun(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50]"
        :total="total"
        layout="total, sizes, prev, pager, next, jumper"
        style="margin-top: 20px; text-align: right"
      />
    </el-card>

    <el-dialog v-model="detailsVisible" title="运行详情" width="70%">
      <div v-if="selectedRun" class="run-details">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="运行ID">{{ selectedRun.id }}</el-descriptions-item>
          <el-descriptions-item label="Agent名称">{{ selectedRun.agent_name }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getStatusType(selectedRun.status)">
              {{ selectedRun.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">{{ selectedRun.created_at }}</el-descriptions-item>
          <el-descriptions-item label="输入" :span="2">
            <pre>{{ selectedRun.input }}</pre>
          </el-descriptions-item>
          <el-descriptions-item label="输出" :span="2">
            <pre>{{ selectedRun.output }}</pre>
          </el-descriptions-item>
        </el-descriptions>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { RunSummary } from '../types'

const runs = ref<RunSummary[]>([])
const filterStatus = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const detailsVisible = ref(false)
const selectedRun = ref<RunSummary | null>(null)

const total = computed(() => runs.value.length)

const filteredRuns = computed(() => {
  let filtered = runs.value
  if (filterStatus.value) {
    filtered = filtered.filter(r => r.status === filterStatus.value)
  }
  const start = (currentPage.value - 1) * pageSize.value
  return filtered.slice(start, start + pageSize.value)
})

onMounted(async () => {
  await refreshRuns()
})

const refreshRuns = async () => {
  // Mock data
  runs.value = [
    {
      id: 'run-001',
      agent_name: 'DataProcessor',
      status: 'success',
      created_at: new Date().toLocaleString(),
      duration: '2m 30s',
      input: '{"data": "sample"}',
      output: '{"result": "processed"}'
    },
    {
      id: 'run-002',
      agent_name: 'WebScraper',
      status: 'success',
      created_at: new Date().toLocaleString(),
      duration: '1m 15s',
      input: '{"url": "https://example.com"}',
      output: '{"pages": 10}'
    },
    {
      id: 'run-003',
      agent_name: 'DataProcessor',
      status: 'failed',
      created_at: new Date().toLocaleString(),
      duration: '30s',
      input: '{"data": "invalid"}',
      output: '{"error": "Invalid input"}'
    }
  ]
}

const getStatusType = (status: string) => {
  switch (status) {
    case 'success':
      return 'success'
    case 'failed':
      return 'danger'
    case 'running':
      return 'warning'
    default:
      return 'info'
  }
}

const viewDetails = (run: RunSummary) => {
  selectedRun.value = run
  detailsVisible.value = true
}

const deleteRun = async (run: RunSummary) => {
  try {
    await ElMessageBox.confirm('确定删除该运行记录吗?', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    runs.value = runs.value.filter(r => r.id !== run.id)
    ElMessage.success('运行记录已删除')
  } catch (e) {
    console.error(e)
  }
}
</script>

<style scoped lang="scss">
.runs-page {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .filters {
      display: flex;
      gap: 10px;
      align-items: center;
    }
  }

  .run-details {
    pre {
      background: var(--el-fill-color-light);
      padding: 10px;
      border-radius: 4px;
      overflow-x: auto;
      max-height: 300px;
    }
  }
}
</style>
