<script setup lang="ts">
import { ArrowLeft, Delete, Edit, RefreshLeft } from '@element-plus/icons-vue'
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import articleApi from '../api'
import type { ArticleDetail } from '../api'

const route = useRoute()
const router = useRouter()

const articleId = Number(route.params.id)
const article = ref<ArticleDetail | null>(null)
const loading = ref(true)

async function load(): Promise<void> {
  loading.value = true
  try {
    const { data } = await articleApi.articles.get(articleId)
    article.value = data
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '文章不存在')
    router.replace({ name: 'article' })
  } finally {
    loading.value = false
  }
}

async function onTrash(): Promise<void> {
  await articleApi.articles.remove(articleId)
  ElMessage.success('已移入回收站')
  router.replace({ name: 'article' })
}

async function onRestore(): Promise<void> {
  await articleApi.articles.restore(articleId)
  ElMessage.success('已还原')
  load()
}

async function onForceDelete(): Promise<void> {
  try {
    await ElMessageBox.confirm('彻底删除后无法恢复。确定吗？', '彻底删除', {
      type: 'warning',
      confirmButtonText: '彻底删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  await articleApi.articles.forceRemove(articleId)
  ElMessage.success('已彻底删除')
  router.replace({ name: 'article' })
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="article-detail">
    <div class="bar">
      <el-button :icon="ArrowLeft" link @click="router.push({ name: 'article' })">
        返回列表
      </el-button>
      <span class="spacer" />

      <template v-if="article">
        <template v-if="article.status === 'deleted'">
          <el-tag type="warning" size="small">在回收站里</el-tag>
          <el-button :icon="RefreshLeft" @click="onRestore">还原</el-button>
          <el-button type="danger" :icon="Delete" @click="onForceDelete">
            彻底删除
          </el-button>
        </template>
        <template v-else>
          <el-button
            :icon="Edit"
            @click="router.push({ name: 'article-edit', params: { id: articleId } })"
          >
            编辑
          </el-button>
          <el-button :icon="Delete" @click="onTrash">删除</el-button>
        </template>
      </template>
    </div>

    <template v-if="article">
      <h1 class="title">{{ article.title }}</h1>

      <div class="meta">
        <el-tag size="small" type="info">{{ article.category.name }}</el-tag>
        <el-tag v-for="t in article.tags" :key="t.id" size="small" effect="plain">
          {{ t.name }}
        </el-tag>
        <span class="time">
          更新于 {{ formatDate(article.updated_at) }}
          <template v-if="article.created_at !== article.updated_at">
            · 创建于 {{ formatDate(article.created_at) }}
          </template>
        </span>
      </div>

      <!--
        v-html 渲染富文本。安全性由**服务端**保证：保存时已经用 nh3 做过
        白名单消毒，script、事件属性、javascript: 链接都被剥掉了。
        前端不要再自作聪明地"再消毒一遍"——那会和后端的白名单各说各话。
      -->
      <article class="content" v-html="article.content_html" />
    </template>
  </div>
</template>

<style scoped>
.article-detail {
  max-width: 800px;
  margin: 0 auto;
}

.bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}

.spacer {
  flex: 1;
}

.title {
  margin: 0 0 12px;
  font-size: 26px;
  line-height: 1.4;
  word-break: break-word;
}

.meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.time {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.content {
  font-size: 15px;
  line-height: 1.9;
  word-break: break-word;
}

/* 富文本内部的元素不在 scoped 作用域里，要用 :deep 才能命中 */
.content :deep(h1),
.content :deep(h2),
.content :deep(h3) {
  margin: 24px 0 12px;
  line-height: 1.5;
}

.content :deep(p) {
  margin: 0 0 14px;
}

.content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
}

.content :deep(blockquote) {
  margin: 14px 0;
  padding: 8px 14px;
  border-left: 3px solid var(--el-border-color);
  color: var(--el-text-color-secondary);
  background: var(--el-fill-color-lighter);
}

.content :deep(pre) {
  padding: 12px;
  border-radius: 4px;
  background: var(--el-fill-color);
  overflow-x: auto;
}

.content :deep(table) {
  border-collapse: collapse;
  width: 100%;
}

.content :deep(th),
.content :deep(td) {
  border: 1px solid var(--el-border-color);
  padding: 6px 10px;
}

@media (max-width: 768px) {
  .title {
    font-size: 21px;
  }
}
</style>
