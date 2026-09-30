<script setup lang="ts">
import { ArrowLeft, Delete, Edit, Plus } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import articleApi from '../api'
import type { Category, Tag } from '../api'

const router = useRouter()

const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])
const newCategory = ref('')
const newTag = ref('')
const loading = ref(false)

/** 后端返回的 detail 是可以直接给用户看的中文，不用自己映射文案 */
function showError(e: any, fallback: string): void {
  ElMessage.error(e?.response?.data?.detail ?? fallback)
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const [c, t] = await Promise.all([articleApi.categories.list(), articleApi.tags.list()])
    categories.value = c.data
    tags.value = t.data
  } finally {
    loading.value = false
  }
}

// ---------- 分类 ----------

async function addCategory(): Promise<void> {
  const name = newCategory.value.trim()
  if (!name) return
  try {
    await articleApi.categories.create(name)
    newCategory.value = ''
    await load()
  } catch (e) {
    showError(e, '添加失败')
  }
}

async function renameCategory(category: Category): Promise<void> {
  let value: string
  try {
    const result = await ElMessageBox.prompt('改成什么名字？', '重命名分类', {
      inputValue: category.name,
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValidator: (v) => (v && v.trim() ? true : '名字不能为空'),
    })
    value = result.value.trim()
  } catch {
    return // 取消
  }

  try {
    await articleApi.categories.update(category.id, { name: value })
    await load()
  } catch (e) {
    showError(e, '重命名失败')
  }
}

async function removeCategory(category: Category): Promise<void> {
  try {
    await ElMessageBox.confirm(`确定删除分类「${category.name}」吗？`, '删除分类', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  try {
    await articleApi.categories.remove(category.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    // 分类下还有文章时后端返回 409，会告诉你还剩多少篇
    showError(e, '删除失败')
  }
}

// ---------- 标签 ----------

async function addTag(): Promise<void> {
  const name = newTag.value.trim()
  if (!name) return
  try {
    await articleApi.tags.create(name)
    newTag.value = ''
    await load()
  } catch (e) {
    showError(e, '添加失败')
  }
}

async function renameTag(tag: Tag): Promise<void> {
  let value: string
  try {
    const result = await ElMessageBox.prompt('改成什么名字？', '重命名标签', {
      inputValue: tag.name,
      confirmButtonText: '保存',
      cancelButtonText: '取消',
      inputValidator: (v) => (v && v.trim() ? true : '名字不能为空'),
    })
    value = result.value.trim()
  } catch {
    return
  }

  try {
    await articleApi.tags.update(tag.id, value)
    await load()
  } catch (e) {
    showError(e, '重命名失败')
  }
}

async function removeTag(tag: Tag): Promise<void> {
  const warn =
    tag.article_count > 0
      ? `标签「${tag.name}」正被 ${tag.article_count} 篇文章使用，删除后会从这些文章上摘掉（文章本身不受影响）。确定吗？`
      : `确定删除标签「${tag.name}」吗？`

  try {
    await ElMessageBox.confirm(warn, '删除标签', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  try {
    await articleApi.tags.remove(tag.id)
    ElMessage.success('已删除')
    await load()
  } catch (e) {
    showError(e, '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading" class="taxonomy">
    <div class="bar">
      <el-button :icon="ArrowLeft" link @click="router.push({ name: 'article' })">
        返回文章
      </el-button>
    </div>

    <h1 class="title">分类与标签</h1>

    <div class="panels">
      <el-card class="panel">
        <template #header>
          <div class="panel-head">
            <span>分类</span>
            <span class="panel-hint">一篇文章只能属于一个分类</span>
          </div>
        </template>

        <div class="adder">
          <el-input
            v-model="newCategory"
            placeholder="新分类名"
            maxlength="50"
            @keyup.enter="addCategory"
          />
          <el-button type="primary" :icon="Plus" @click="addCategory">添加</el-button>
        </div>

        <el-empty v-if="categories.length === 0" description="还没有分类" :image-size="60" />

        <div v-for="c in categories" :key="c.id" class="row">
          <span class="row-name">{{ c.name }}</span>
          <span class="row-count">{{ c.article_count }} 篇</span>
          <el-button :icon="Edit" link @click="renameCategory(c)" />
          <el-button :icon="Delete" link @click="removeCategory(c)" />
        </div>
      </el-card>

      <el-card class="panel">
        <template #header>
          <div class="panel-head">
            <span>标签</span>
            <span class="panel-hint">一篇文章可以有多个标签</span>
          </div>
        </template>

        <div class="adder">
          <el-input
            v-model="newTag"
            placeholder="新标签名"
            maxlength="50"
            @keyup.enter="addTag"
          />
          <el-button type="primary" :icon="Plus" @click="addTag">添加</el-button>
        </div>

        <el-empty v-if="tags.length === 0" description="还没有标签" :image-size="60" />

        <div v-for="t in tags" :key="t.id" class="row">
          <span class="row-name">{{ t.name }}</span>
          <span class="row-count">{{ t.article_count }} 篇</span>
          <el-button :icon="Edit" link @click="renameTag(t)" />
          <el-button :icon="Delete" link @click="removeTag(t)" />
        </div>
      </el-card>
    </div>

    <p class="hint">
      分类下面还有文章时删不掉，会告诉你还剩多少篇 —— 这是数据库没启用外键校验的
      直接后果，删除前必须自己检查，否则那些文章会变成分类显示不出来的孤儿。
    </p>
  </div>
</template>

<style scoped>
.taxonomy {
  max-width: 900px;
  margin: 0 auto;
}

.bar {
  margin-bottom: 8px;
}

.title {
  margin: 0 0 20px;
  font-size: 22px;
}

.panels {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.panel-hint {
  font-size: 12px;
  font-weight: normal;
  color: var(--el-text-color-secondary);
}

.adder {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.row-name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row-count {
  flex: none;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.hint {
  margin-top: 20px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-text-color-secondary);
}

@media (max-width: 768px) {
  .panels {
    grid-template-columns: 1fr;
  }
}
</style>
