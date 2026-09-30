<script setup lang="ts">
import { ArrowLeft, Refresh } from '@element-plus/icons-vue'
import { computed, onMounted, onUnmounted, ref } from 'vue'

import aiApi from '../api'
import type { KbStatus, RebuildProgress } from '../api'

const status = ref<KbStatus | null>(null)
const progress = ref<RebuildProgress | null>(null)
const loading = ref(false)
const starting = ref(false)

let timer: ReturnType<typeof setInterval> | null = null

const running = computed(() => progress.value?.status === 'running')

/** 进度百分比。total 还是 0（刚开始）时给 0，避免出现 NaN 或者一上来就 100%。 */
const percent = computed(() => {
  const p = progress.value
  if (!p || p.total === 0) return 0
  return Math.min(100, Math.round((p.done / p.total) * 100))
})

const STATUS_TEXT: Record<string, string> = {
  idle: '还没建过索引',
  running: '正在重建',
  done: '已完成',
  failed: '失败',
  interrupted: '被中断',
}

function fmt(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadStatus(): Promise<void> {
  try {
    status.value = (await aiApi.kb.status()).data
  } catch {
    ElMessage.error('读取知识库状态失败')
  }
}

async function loadProgress(): Promise<void> {
  try {
    progress.value = (await aiApi.kb.progress()).data
  } catch {
    /* 轮询失败不打扰用户，下一轮会再试 */
  }
}

function startPolling(): void {
  if (timer) return
  // 1.5 秒一次。重建是分钟级的，这个频率足够让进度条动起来，
  // 又不会把请求打得太多。
  timer = setInterval(async () => {
    await loadProgress()
    if (!running.value) {
      stopPolling()
      // 跑完之后状态（分块数、重建时间）会变，重新拉一次
      await loadStatus()
      ElMessage.success('知识库已更新')
    }
  }, 1500)
}

function stopPolling(): void {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
}

async function rebuild(): Promise<void> {
  starting.value = true
  try {
    progress.value = (await aiApi.kb.rebuild()).data
    startPolling()
  } catch (e: any) {
    // 409 = 已经有一个在跑了（可能是别的标签页触发的），
    // 这不是错误，跟着看进度就行
    if (e?.response?.status === 409) {
      ElMessage.info('已经有一个重建任务在进行中')
      await loadProgress()
      startPolling()
    } else {
      ElMessage.error(e?.response?.data?.detail ?? '触发重建失败')
    }
  } finally {
    starting.value = false
  }
}

async function refresh(): Promise<void> {
  loading.value = true
  await Promise.all([loadStatus(), loadProgress()])
  if (running.value) startPolling()
  loading.value = false
}

onMounted(refresh)
onUnmounted(stopPolling)
</script>

<template>
  <div class="kb" v-loading="loading">
    <div class="head">
      <el-button :icon="ArrowLeft" link @click="$router.push('/ai')">返回问答</el-button>
      <h1 class="title">知识库</h1>
      <el-button :icon="Refresh" link @click="refresh">刷新</el-button>
    </div>

    <!-- 换了 embedding 模型但没重建 —— 这件事必须显眼地提示，
         因为不重建不会报错，只会让检索结果莫名其妙 -->
    <el-alert
      v-if="status && status.stale_chunk_count > 0"
      type="warning"
      :closable="false"
      show-icon
      class="block"
      title="有分块是用旧模型生成的，需要重建"
    >
      知识库里有 {{ status.stale_chunk_count }} 个分块不是用当前的
      <code>{{ status.embedding_model }}</code> 生成的。它们的向量和新问题
      不在同一个向量空间里，<b>参与检索会返回无关内容而且不会报错</b>，
      所以现在被排除在检索之外 —— 点下面的按钮重建即可修复。
    </el-alert>

    <el-alert
      v-if="status?.last_error && !running"
      type="error"
      :closable="false"
      show-icon
      class="block"
      title="上一次重建有问题"
    >
      {{ status.last_error }}
    </el-alert>

    <el-card class="block">
      <template #header>
        <div class="card-head">
          <span>当前状态</span>
          <el-tag
            v-if="progress"
            :type="progress.status === 'failed' ? 'danger' : running ? 'warning' : 'success'"
            size="small"
            disable-transitions
          >
            {{ STATUS_TEXT[progress.status] ?? progress.status }}
          </el-tag>
        </div>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="可检索文章">
          {{ status?.article_count ?? '—' }} 篇
        </el-descriptions-item>
        <el-descriptions-item label="知识库分块">
          {{ status?.chunk_count ?? '—' }} 块
        </el-descriptions-item>
        <el-descriptions-item label="向量模型">
          {{ status?.embedding_model ?? '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="向量维度">
          {{ status?.embedding_dim ?? '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="上次重建" :span="2">
          {{ fmt(status?.last_rebuilt_at ?? null) }}
        </el-descriptions-item>
      </el-descriptions>

      <div v-if="running && progress" class="prog">
        <el-progress :percentage="percent" :stroke-width="14" />
        <div class="prog-text">
          正在处理 {{ progress.done }} / {{ progress.total }} 篇
          <span v-if="progress.failed > 0" class="prog-fail">
            （{{ progress.failed }} 篇失败）
          </span>
          　这期间可以先去做别的，关掉页面进度也不会丢
        </div>
      </div>

      <div class="actions">
        <el-button
          type="primary"
          :icon="Refresh"
          :loading="starting || running"
          :disabled="running"
          @click="rebuild"
        >
          {{ running ? '正在重建…' : '重建索引' }}
        </el-button>
        <span class="hint">
          全量重建：把所有文章的正文重新切块、重新向量化。
          文章改动之后需要点一次，索引才会跟上。
        </span>
      </div>
    </el-card>

    <el-card class="block">
      <template #header>关于切块</template>
      <p class="para">
        文章正文按段落切成约 <b>500 字</b> 的块，相邻两块重叠约 <b>100 字</b> ——
        防止答案正好被切在边界上、两边都不完整。
      </p>
      <p class="para">
        每块的开头都带上<b>文章标题</b>。标题是最强的检索信号：
        问「租房合同要注意什么」时，标题里就有这几个字的文章应该排前面，
        而正文可能通篇在讲押金、违约、退租，一次都没提「租房合同」四个字。
      </p>
      <p class="para">
        只有<b>纯文本正文</b>会进知识库，富文本里的 HTML 标签不会 ——
        标签会污染语义匹配。
      </p>
    </el-card>
  </div>
</template>

<style scoped>
.kb {
  max-width: 760px;
  margin: 0 auto;
}

.head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.title {
  flex: 1;
  margin: 0;
  font-size: 22px;
}

.block {
  margin-bottom: 16px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.prog {
  margin-top: 16px;
}

.prog-text {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.prog-fail {
  color: var(--el-color-danger);
}

.actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.hint {
  flex: 1;
  min-width: 200px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}

.para {
  margin: 0 0 10px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--el-text-color-regular);
}

.para:last-child {
  margin-bottom: 0;
}
</style>
