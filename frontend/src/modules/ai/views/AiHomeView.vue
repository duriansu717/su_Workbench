<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { aiApi } from '../api'

/** 骨架占位页，用来验证本模块的前后端链路是通的。 */
const message = ref('')
const error = ref('')

onMounted(async () => {
  try {
    const { data } = await aiApi.ping()
    message.value = data.message
  } catch {
    error.value = '接口调不通，检查后端是否在 8000 端口运行'
  }
})
</script>

<template>
  <div>
    <h1 class="title">问答</h1>

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

    <el-empty description="骨架占位页。知识库构建与智能问答在第三期实现。" />
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
