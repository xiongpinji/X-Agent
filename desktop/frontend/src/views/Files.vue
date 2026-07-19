<template>
  <div class="files-page">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>文件浏览</span>
          <div class="actions">
            <el-input
              v-model="currentPath"
              placeholder="输入路径"
              style="width: 300px"
              @keyup.enter="navigateTo"
            />
            <el-button @click="refreshFiles">刷新</el-button>
            <el-button @click="createFolder">新建文件夹</el-button>
          </div>
        </div>
      </template>

      <el-breadcrumb separator="/" style="margin-bottom: 20px">
        <el-breadcrumb-item @click="navigateTo('/')">根目录</el-breadcrumb-item>
        <el-breadcrumb-item
          v-for="(part, index) in breadcrumbs"
          :key="index"
          @click="navigateTo(part.path)"
        >
          {{ part.name }}
        </el-breadcrumb-item>
      </el-breadcrumb>

      <el-table :data="files" stripe>
        <el-table-column prop="name" label="名称" width="300">
          <template #default="{ row }">
            <div class="file-name">
              <i :class="row.is_dir ? 'el-icon-folder' : 'el-icon-document'"></i>
              <span @click="openFile(row)" style="cursor: pointer; color: var(--el-color-primary)">
                {{ row.name }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="size" label="大小" width="120">
          <template #default="{ row }">
            {{ formatSize(row.size) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            <el-button type="danger" size="small" @click="deleteFile(row)">
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { invoke } from '@tauri-apps/api/tauri'
import { ElMessage, ElMessageBox } from 'element-plus'

const currentPath = ref('/')
const files = ref([])

const breadcrumbs = computed(() => {
  const parts = currentPath.value.split('/').filter(p => p)
  let path = ''
  return parts.map(part => {
    path += '/' + part
    return { name: part, path }
  })
})

onMounted(async () => {
  await loadFiles()
})

const loadFiles = async () => {
  try {
    const result = await invoke('list_directory', { path: currentPath.value })
    files.value = result
  } catch (e) {
    ElMessage.error('加载文件列表失败')
    console.error(e)
  }
}

const navigateTo = async (path?: string) => {
  if (path) {
    currentPath.value = path
  }
  await loadFiles()
}

const refreshFiles = async () => {
  await loadFiles()
}

const createFolder = async () => {
  ElMessage.info('创建文件夹功能开发中...')
}

const openFile = async (file: any) => {
  if (file.is_dir) {
    currentPath.value = file.path
    await loadFiles()
  } else {
    ElMessage.info('打开文件功能开发中...')
  }
}

const deleteFile = async (file: any) => {
  try {
    await ElMessageBox.confirm('确定删除该文件吗?', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })

    if (file.is_dir) {
      await invoke('delete_directory', { path: file.path })
    } else {
      await invoke('delete_file', { path: file.path })
    }

    ElMessage.success('文件已删除')
    await loadFiles()
  } catch (e) {
    console.error(e)
  }
}

const formatSize = (bytes: number) => {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i]
}
</script>

<style scoped lang="scss">
.files-page {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .actions {
      display: flex;
      gap: 10px;
      align-items: center;
    }
  }

  .file-name {
    display: flex;
    align-items: center;
    gap: 8px;
  }
}
</style>
