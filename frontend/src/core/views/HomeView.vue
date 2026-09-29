<script setup lang="ts">
import { onMounted, ref } from 'vue'

import api from '../api'
import { getModules } from '../registry'

interface BackendModule {
  name: string
  title: string
  prefix: string
}

/**
 * 首页。模块卡片来自前端注册表，同时探一次后端 /api/health。
 *
 * 这个健康检查是骨架阶段的验收手段：它同时验证了「后端起来了」和
 * 「模块注册表在后端也生效了」两件事。功能都接上以后可以保留，
 * 也可以改成更有用的信息。
 */
const modules = getModules()
const backendModules = ref<BackendModule[] | null>(null)
const backendError = ref('')

onMounted(async () => {
  try {
    const { data } = await api.get<{ modules: BackendModule[] }>('/health')
    backendModules.value = data.modules
  } catch {
    backendError.value = '连不上后端。确认 uvicorn 已在 8000 端口启动。'
  }
})
</script>

<template>
  <div class="home">
    <h1 class="title">工作台</h1>

    <el-alert
      v-if="backendError"
      :title="backendError"
      type="error"
      :closable="false"
      show-icon
      class="status"
    />
    <el-alert
      v-else-if="backendModules"
      :title="`后端已连通，注册了 ${backendModules.length} 个模块：${backendModules
        .map((m) => m.title)
        .join('、')}`"
      type="success"
      :closable="false"
      show-icon
      class="status"
    />

    <div class="cards">
      <router-link v-for="m in modules" :key="m.name" :to="`/${m.name}`" class="card-link">
        <el-card shadow="hover" class="card">
          <div class="card-head">
            <el-icon :size="22"><component :is="m.icon" /></el-icon>
            <span class="card-title">{{ m.title }}</span>
          </div>
          <p class="card-desc">{{ m.description }}</p>
        </el-card>
      </router-link>
    </div>
  </div>
</template>

<style scoped>
.title {
  margin: 0 0 16px;
  font-size: 22px;
}

.status {
  margin-bottom: 16px;
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 16px;
}

.card-link {
  text-decoration: none;
  color: inherit;
}

.card-head {
  display: flex;
  align-items: center;
  gap: 8px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.card-desc {
  margin: 10px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--el-text-color-secondary);
}
</style>
