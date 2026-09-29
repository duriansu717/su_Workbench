<template>
  <div class="not-found">
    <el-result icon="warning" title="页面不存在" sub-title="检查一下地址，或者回到首页">
      <template #extra>
        <router-link to="/">
          <el-button type="primary">回首页</el-button>
        </router-link>
      </template>
    </el-result>
  </div>
</template>

<style scoped>
.not-found {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
}
</style>
