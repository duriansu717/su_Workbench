<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { planApi } from '../api'

/** 骨架占位页，用来验证本模块的前后端链路是通的。 */
const message = ref('')
const error = ref('')

onMounted(async () => {
  try {
    const { data } = await planApi.ping()
    message.value = data.message
  } catch {
    error.value = '接口调不通，检查后端是否在 8000 端口运行'
  }
})
</script>

<template>
  <div>
    <h1 class="title">计划</h1>

    <el-alert
      v-if="error"
      :title="error"
      type="error"
      :closable="false"
      show-icon
      class="status"
    />
    <el-alert
      v-else-if="message"
      :title="message"
      type="success"
      :closable="false"
      show-icon
      class="status"
    />

    <el-empty description="骨架占位页。待办清单和日 / 周 / 月计划表在后续阶段实现。" />
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
</style>
