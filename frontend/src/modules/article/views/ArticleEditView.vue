<script setup lang="ts">
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import articleApi from '../api'
import type { Category, Tag } from '../api'
import RichEditor from '../components/RichEditor.vue'

const route = useRoute()
const router = useRouter()

const articleId = route.params.id ? Number(route.params.id) : null
const isEdit = articleId !== null

/** 编辑器要等数据都到位了再渲染 —— 见下面 onMounted 的说明。 */
const loaded = ref(false)
const saving = ref(false)
const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])

const form = reactive({
  title: '',
  content_html: '<p><br></p>',
  category_id: null as number | null,
  tag_ids: [] as number[],
})

const noCategory = computed(() => categories.value.length === 0)

/** 富文本里可能只有空标签，剥掉标签后为空才算真的没写内容 */
function hasContent(): boolean {
  return form.content_html.replace(/<[^>]*>/g, '').replace(/&nbsp;/g, '').trim().length > 0
}

async function save(): Promise<void> {
  if (!form.title.trim()) {
    ElMessage.warning('标题不能为空')
    return
  }
  if (form.category_id === null) {
    ElMessage.warning('请选择分类')
    return
  }
  if (!hasContent()) {
    ElMessage.warning('正文不能为空')
    return
  }

  saving.value = true
  try {
    const payload = {
      title: form.title.trim(),
      content_html: form.content_html,
      category_id: form.category_id,
      tag_ids: form.tag_ids,
    }
    const { data } = isEdit
      ? await articleApi.articles.update(articleId!, payload)
      : await articleApi.articles.create(payload)

    ElMessage.success(isEdit ? '已保存' : '已创建')
    await router.replace({ name: 'article-detail', params: { id: data.id } })
  } catch (e: any) {
    // 后端的 detail 是可以直接给用户看的中文，不用自己映射文案
    ElMessage.error(e?.response?.data?.detail ?? '保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  const [c, t] = await Promise.all([articleApi.categories.list(), articleApi.tags.list()])
  categories.value = c.data
  tags.value = t.data

  if (isEdit) {
    const { data } = await articleApi.articles.get(articleId!)
    form.title = data.title
    form.content_html = data.content_html
    form.category_id = data.category.id
    form.tag_ids = data.tags.map((tag) => tag.id)
  } else if (categories.value.length === 1) {
    // 只有一个分类时不用让用户再点一下
    form.category_id = categories.value[0].id
  }

  // ★ 数据全部到位后才渲染编辑器。
  // 编辑器是拿 v-model 接管内容的，如果在它初始化之后再异步塞初始值，
  // 会出现"界面上有内容但编辑器内部状态还是空的"，保存后正文丢失。
  loaded.value = true
})
</script>

<template>
  <div class="article-edit">
    <div class="bar">
      <el-button :icon="ArrowLeft" link @click="router.back()">返回</el-button>
      <span class="spacer" />
      <el-button type="primary" :loading="saving" :disabled="noCategory" @click="save">
        {{ isEdit ? '保存' : '创建' }}
      </el-button>
    </div>

    <el-alert
      v-if="noCategory"
      type="warning"
      show-icon
      :closable="false"
      class="notice"
    >
      <template #title>
        还没有任何分类，没法新建文章。
        <el-link type="primary" @click="router.push({ name: 'article-taxonomy' })">
          先去建一个分类
        </el-link>
      </template>
    </el-alert>

    <el-input
      v-model="form.title"
      placeholder="标题"
      size="large"
      maxlength="200"
      show-word-limit
      class="title-input"
    />

    <div class="row">
      <el-select v-model="form.category_id" placeholder="选择分类" class="picker">
        <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
      </el-select>

      <el-select
        v-model="form.tag_ids"
        multiple
        filterable
        clearable
        placeholder="标签（可多选，也可以直接输入新建）"
        class="tag-picker"
      >
        <el-option v-for="t in tags" :key="t.id" :label="t.name" :value="t.id" />
      </el-select>
    </div>

    <RichEditor v-if="loaded" v-model="form.content_html" />

    <p class="hint">
      保存时正文会自动过滤掉脚本等危险内容，并生成一份纯文本副本供搜索和以后的
      AI 问答使用 —— 这些都是服务端做的，你只管写。
    </p>
  </div>
</template>

<style scoped>
.article-edit {
  max-width: 900px;
  margin: 0 auto;
}

.bar {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}

.spacer {
  flex: 1;
}

.notice {
  margin-bottom: 16px;
}

.title-input {
  margin-bottom: 12px;
}

.row {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.picker {
  width: 180px;
  flex: none;
}

.tag-picker {
  flex: 1;
  min-width: 0;
}

.hint {
  margin-top: 12px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--el-text-color-secondary);
}

@media (max-width: 768px) {
  .row {
    flex-direction: column;
  }

  .picker {
    width: 100%;
  }
}
</style>
