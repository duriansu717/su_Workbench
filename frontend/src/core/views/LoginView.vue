<script setup lang="ts">
import { Lock, User } from '@element-plus/icons-vue'
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const form = reactive({ username: '', password: '' })
const error = ref('')
const loading = ref(false)

async function submit(): Promise<void> {
  if (loading.value) return

  error.value = ''
  loading.value = true
  try {
    await auth.login(form.username, form.password)

    // 被守卫拦下来时记下的目标地址，登录后回到那里；没有就去首页
    const redirect = route.query.redirect
    await router.replace(typeof redirect === 'string' ? redirect : '/')
  } catch (e: any) {
    // 错误直接显示在表单里，不用 ElMessage 弹窗 ——
    // 登录失败是高频操作，弹窗要点一下才能重试，表单内提示更顺手
    error.value =
      e?.response?.status === 401
        ? '账号或密码不对'
        : '登录失败，确认后端是否在 8000 端口运行'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card">
      <h1 class="title">工作台</h1>
      <p class="subtitle">登录后继续</p>

      <el-form @submit.prevent="submit">
        <el-input
          v-model="form.username"
          placeholder="账号"
          size="large"
          :prefix-icon="User"
          autocomplete="username"
          class="field"
        />
        <el-input
          v-model="form.password"
          type="password"
          placeholder="密码"
          size="large"
          :prefix-icon="Lock"
          show-password
          autocomplete="current-password"
          class="field"
          @keyup.enter="submit"
        />

        <el-alert
          v-if="error"
          :title="error"
          type="error"
          :closable="false"
          show-icon
          class="field"
        />

        <el-button
          type="primary"
          size="large"
          class="field submit"
          :loading="loading"
          @click="submit"
        >
          登录
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 16px;
}

.login-card {
  width: 100%;
  max-width: 360px;
}

.title {
  margin: 0;
  font-size: 22px;
  text-align: center;
}

.subtitle {
  margin: 6px 0 24px;
  font-size: 13px;
  text-align: center;
  color: var(--el-text-color-secondary);
}

.field {
  margin-bottom: 16px;
  width: 100%;
}

.submit {
  margin-bottom: 0;
}
</style>
