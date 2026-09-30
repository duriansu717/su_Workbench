<script setup lang="ts">
import { Delete, Edit, MagicStick, Plus, RefreshLeft, Search } from '@element-plus/icons-vue'
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import articleApi from '../api'
import type { ArticleListItem, Category, Tag } from '../api'

const router = useRouter()

const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])
const items = ref<ArticleListItem[]>([])
const total = ref(0)
const loading = ref(false)

const query = reactive({
  page: 1,
  page_size: 10,
  keyword: '',
  category_id: null as number | null,
  tag_id: null as number | null,
  status: 'published' as 'published' | 'deleted',
})

const isTrash = () => query.status === 'deleted'

async function loadTaxonomy(): Promise<void> {
  const [c, t] = await Promise.all([articleApi.categories.list(), articleApi.tags.list()])
  categories.value = c.data
  tags.value = t.data
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const { data } = await articleApi.articles.list({
      page: query.page,
      page_size: query.page_size,
      keyword: query.keyword || undefined,
      category_id: query.category_id ?? undefined,
      tag_id: query.tag_id ?? undefined,
      status: query.status,
    })
    items.value = data.items
    total.value = data.total
  } catch {
    ElMessage.error('加载文章列表失败')
  } finally {
    loading.value = false
  }
}

/** 换筛选条件时回到第一页 —— 否则会停在一个已经不存在的页码上 */
function reload(): void {
  query.page = 1
  load()
}

function switchStatus(): void {
  query.category_id = null
  query.tag_id = null
  reload()
}

async function onTrash(id: number): Promise<void> {
  await articleApi.articles.remove(id)
  ElMessage.success('已移入回收站')
  load()
}

async function onRestore(id: number): Promise<void> {
  await articleApi.articles.restore(id)
  ElMessage.success('已还原')
  load()
}

async function onForceDelete(id: number): Promise<void> {
  try {
    await ElMessageBox.confirm(
      '彻底删除后无法恢复，连回收站里也找不回来。确定吗？',
      '彻底删除',
      { type: 'warning', confirmButtonText: '彻底删除', cancelButtonText: '取消' },
    )
  } catch {
    return // 用户点了取消
  }
  await articleApi.articles.forceRemove(id)
  ElMessage.success('已彻底删除')
  load()
}

function formatDate(iso: string): string {
  // 后端返回的是带 Z 的 UTC 时间，new Date 会正确转成本地时区显示
  return new Date(iso).toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(async () => {
  await loadTaxonomy()
  await load()
})
</script>

<template>
  <div class="article-list">
    <div class="head">
      <h1 class="title">文章</h1>
      <div class="actions">
        <el-button :icon="MagicStick" @click="router.push({ name: 'article-taxonomy' })">
          分类与标签
        </el-button>
        <el-button type="primary" :icon="Plus" @click="router.push({ name: 'article-new' })">
          新建文章
        </el-button>
      </div>
    </div>

    <div class="filters">
      <el-radio-group v-model="query.status" @change="switchStatus">
        <el-radio-button value="published">文章</el-radio-button>
        <el-radio-button value="deleted">回收站</el-radio-button>
      </el-radio-group>

      <el-input
        v-model="query.keyword"
        placeholder="搜标题和正文"
        :prefix-icon="Search"
        clearable
        class="search"
        @keyup.enter="reload"
        @clear="reload"
      />

      <el-select
        v-model="query.category_id"
        placeholder="全部分类"
        clearable
        class="picker"
        @change="reload"
      >
        <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>

      <el-select
        v-model="query.tag_id"
        placeholder="全部标签"
        clearable
        class="picker"
        @change="reload"
      >
        <el-option
          v-for="t in tags"
          :key="t.id"
          :label="`${t.name} (${t.article_count})`"
          :value="t.id"
        />
      </el-select>

      <el-button @click="reload">查询</el-button>
    </div>

    <div v-loading="loading" class="list">
      <el-empty
        v-if="!loading && items.length === 0"
        :description="isTrash() ? '回收站是空的' : '还没有文章，点右上角新建一篇'"
      />

      <el-card
        v-for="item in items"
        :key="item.id"
        shadow="hover"
        class="item"
        @click="router.push({ name: 'article-detail', params: { id: item.id } })"
      >
        <div class="item-head">
          <span class="item-title">{{ item.title }}</span>
          <span class="item-date">{{ formatDate(item.updated_at) }}</span>
        </div>

        <p class="item-excerpt">{{ item.excerpt }}</p>

        <div class="item-foot">
          <el-tag size="small" type="info">{{ item.category.name }}</el-tag>
          <el-tag v-for="t in item.tags" :key="t.id" size="small" effect="plain">
            {{ t.name }}
          </el-tag>

          <span class="spacer" />

          <template v-if="isTrash()">
            <el-button
              size="small"
              :icon="RefreshLeft"
              @click.stop="onRestore(item.id)"
            >
              还原
            </el-button>
            <el-button
              size="small"
              type="danger"
              :icon="Delete"
              @click.stop="onForceDelete(item.id)"
            >
              彻底删除
            </el-button>
          </template>
          <template v-else>
            <el-button
              size="small"
              :icon="Edit"
              @click.stop="router.push({ name: 'article-edit', params: { id: item.id } })"
            >
              编辑
            </el-button>
            <el-button size="small" :icon="Delete" @click.stop="onTrash(item.id)">
              删除
            </el-button>
          </template>
        </div>
      </el-card>
    </div>

    <el-pagination
      v-if="total > query.page_size"
      v-model:current-page="query.page"
      :page-size="query.page_size"
      :total="total"
      layout="prev, pager, next"
      class="pager"
      @current-change="load"
    />
  </div>
</template>

<style scoped>
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 16px;
}

.title {
  margin: 0;
  font-size: 22px;
}

.actions {
  display: flex;
  gap: 8px;
}

.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}

.search {
  width: 220px;
}

.picker {
  width: 150px;
}

.list {
  min-height: 200px;
}

.item {
  margin-bottom: 12px;
  cursor: pointer;
}

.item-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.item-title {
  font-size: 16px;
  font-weight: 600;
}

.item-date {
  flex: none;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.item-excerpt {
  margin: 8px 0 12px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--el-text-color-regular);
  /* 摘要最多两行，超出省略 */
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  white-space: pre-wrap;
}

.item-foot {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.spacer {
  flex: 1;
}

.pager {
  justify-content: center;
  margin-top: 16px;
}

@media (max-width: 768px) {
  .search,
  .picker {
    width: 100%;
  }
}
</style>
