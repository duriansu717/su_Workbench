<script setup lang="ts">
import SideNav from './SideNav.vue'
</script>

<template>
  <div class="app-shell">
    <aside class="app-side">
      <SideNav />
    </aside>
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.app-shell {
  display: flex;
  min-height: 100vh;
}

.app-side {
  flex: 0 0 200px;
  width: 200px;
  border-right: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
}

.app-main {
  flex: 1;
  min-width: 0;
  padding: 20px;
}

/* 手机端：侧边栏变成顶部横向条。整个应用只有这一个断点，
   小屏下优先保证阅读、搜索和勾选待办的体验，重度编辑留给桌面端。 */
@media (max-width: 768px) {
  .app-shell {
    flex-direction: column;
  }

  .app-side {
    flex: none;
    width: 100%;
    border-right: none;
    border-bottom: 1px solid var(--el-border-color-lighter);
    position: sticky;
    top: 0;
    z-index: 10;
  }

  .app-main {
    padding: 12px;
  }
}
</style>
