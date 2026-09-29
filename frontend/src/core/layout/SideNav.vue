<script setup lang="ts">
import { HomeFilled } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { getModules } from '../registry'
import { useAuthStore } from '../stores/auth'

/**
 * 导航菜单。
 *
 * 菜单项完全由模块注册表生成，这里不写死任何模块的链接 ——
 * 新增模块只要登记进注册表，菜单里自动就出现了。
 */
const modules = computed(() => getModules())
const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

/** el-menu 需要一个「当前该高亮哪一项」的值。 */
const activeIndex = computed(() => {
  const match = modules.value.find((m) => route.path.startsWith(`/${m.name}`))
  return match ? `/${match.name}` : '/'
})

async function onLogout(): Promise<void> {
  await auth.logout()
  await router.replace({ name: 'login' })
}
</script>

<template>
  <div class="side-nav">
    <div class="brand">
      <span class="brand-name">工作台</span>
      <el-button link size="small" @click="onLogout">退出</el-button>
    </div>

    <el-menu :default-active="activeIndex" router class="nav-menu">
      <el-menu-item index="/">
        <el-icon><HomeFilled /></el-icon>
        <span>首页</span>
      </el-menu-item>

      <el-menu-item v-for="m in modules" :key="m.name" :index="`/${m.name}`">
        <el-icon><component :is="m.icon" /></el-icon>
        <span>{{ m.title }}</span>
      </el-menu-item>
    </el-menu>
  </div>
</template>

<style scoped>
.brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 16px 10px 20px;
}

.brand-name {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: 1px;
}

.nav-menu {
  border-right: none;
}

@media (max-width: 768px) {
  .brand {
    padding: 10px 12px 4px 16px;
  }

  .brand-name {
    font-size: 14px;
  }

  /* 手机端把菜单横向铺开，省掉垂直空间 */
  .nav-menu {
    display: flex;
    overflow-x: auto;
  }

  .nav-menu :deep(.el-menu-item) {
    border-bottom: 2px solid transparent;
  }
}
</style>
