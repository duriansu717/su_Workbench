<script setup lang="ts">
import { ChatLineRound, Delete, Plus, Promotion, Setting, VideoPause } from '@element-plus/icons-vue'
import { computed, nextTick, onMounted, ref } from 'vue'

import aiApi from '../api'
import type { ChatMessage, ChatSession, Citation } from '../api'
import { streamChat } from '../chat'

const sessions = ref<ChatSession[]>([])
const currentId = ref<number | null>(null)
const messages = ref<ChatMessage[]>([])

const input = ref('')
const streaming = ref(false)
/** 流式过程中累积的回答。**在落库之前它就是这条助手消息的全部内容** */
const pending = ref<ChatMessage | null>(null)

const listOpen = ref(false)
const scroller = ref<HTMLElement | null>(null)
let abort: AbortController | null = null

const canSend = computed(() => input.value.trim().length > 0 && !streaming.value)
const isEmpty = computed(() => messages.value.length === 0 && !pending.value)

/**
 * 把模型返回的文本变成可以安全 v-html 的 HTML。
 *
 * ★ **先转义、再做格式替换**，顺序不能反 —— 反过来的话，文本里如果有
 *   `<script>` 就会先被当成标签，转义反而把尖括号留下了。
 *   本项目其它地方对 HTML 的态度是「后端用 nh3 白名单过滤」，
 *   这里内容来自模型而非用户输入，风险本就低，但仍然按最保守的做法来。
 *
 * 只处理 **加粗** 一种标记。列表、标题一律按纯文本显示（容器上有 pre-wrap，
 * 换行和缩进都保留）—— 为聊天窗引入一个完整的 markdown 渲染器不划算。
 */
function renderText(text: string): string {
  const escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  return escaped.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
}

async function scrollToBottom(): Promise<void> {
  await nextTick()
  const el = scroller.value
  if (el) el.scrollTop = el.scrollHeight
}

async function loadSessions(): Promise<void> {
  try {
    sessions.value = (await aiApi.sessions.list()).data
  } catch {
    ElMessage.error('加载会话列表失败')
  }
}

async function openSession(id: number): Promise<void> {
  if (streaming.value) return
  currentId.value = id
  listOpen.value = false
  try {
    const { data } = await aiApi.sessions.get(id)
    messages.value = data.messages
    scrollToBottom()
  } catch {
    ElMessage.error('打开会话失败')
  }
}

function newSession(): void {
  if (streaming.value) return
  // 不立刻建 —— 建会话的接口要标题，而标题得从第一句提问里取。
  // 所以这里只是清空界面，真正的创建推迟到第一次发送时（见 ensureSession）。
  currentId.value = null
  messages.value = []
  input.value = ''
  listOpen.value = false
}

async function ensureSession(question: string): Promise<number> {
  if (currentId.value !== null) return currentId.value

  // ★ 用首句提问的前 20 个字当标题。**不调模型生成标题** ——
  //   那要多花一次调用、一次额度和一次延迟，只为了列表里好看一点。
  const title = question.length > 20 ? `${question.slice(0, 20)}…` : question
  const { data } = await aiApi.sessions.create(title)
  currentId.value = data.id
  await loadSessions()
  return data.id
}

async function send(): Promise<void> {
  const question = input.value.trim()
  if (!question || streaming.value) return

  let sessionId: number
  try {
    sessionId = await ensureSession(question)
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail ?? '创建会话失败')
    return
  }

  input.value = ''
  // 先把用户消息放进界面，不等服务端回应 —— 否则打字之后界面毫无反馈
  messages.value.push({
    id: -Date.now(),
    role: 'user',
    content: question,
    used_knowledge: true,
    citations: [],
    created_at: new Date().toISOString(),
  })

  // 助手的占位消息。citations 一开始是空的，
  // meta 事件一到就填上 —— **不用等回答生成完**。
  pending.value = {
    id: -1,
    role: 'assistant',
    content: '',
    used_knowledge: true,
    citations: [],
    created_at: new Date().toISOString(),
  }
  streaming.value = true
  abort = new AbortController()
  await scrollToBottom()

  await streamChat(
    sessionId,
    question,
    {
      onMeta(used, citations) {
        if (!pending.value) return
        pending.value.used_knowledge = used
        pending.value.citations = citations
        scrollToBottom()
      },
      onDelta(text) {
        if (!pending.value) return
        pending.value.content += text
        scrollToBottom()
      },
      onDone() {
        finishStreaming()
      },
      onError(detail) {
        ElMessage.error(detail)
        finishStreaming()
      },
    },
    abort.signal,
  )

  // 请求正常结束但没收到 done（比如被取消），也要收尾
  if (streaming.value) finishStreaming()
}

function finishStreaming(): void {
  streaming.value = false
  abort = null
  if (pending.value && pending.value.content) {
    messages.value.push(pending.value)
  }
  pending.value = null
  scrollToBottom()
}

function stop(): void {
  abort?.abort()
  // 已经生成的部分会被服务端存下来（见 ai/service.py），
  // 但界面上的这一条先就地保留，用户不用刷新就能看到已经拿到的内容
  finishStreaming()
  ElMessage.info('已停止，已生成的部分会保留')
}

async function removeSession(session: ChatSession): Promise<void> {
  try {
    await ElMessageBox.confirm(`删除会话「${session.title}」？`, '删除会话', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }

  try {
    await aiApi.sessions.remove(session.id)
  } catch {
    ElMessage.error('删除失败')
    return
  }

  if (currentId.value === session.id) newSession()
  await loadSessions()
  ElMessage.success('已删除')
}

function scoreTag(score: number): 'success' | 'warning' | 'info' {
  if (score >= 0.6) return 'success'
  if (score >= 0.45) return 'warning'
  return 'info'
}

function shortTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

onMounted(loadSessions)
</script>

<template>
  <div class="chat">
    <!-- 左侧会话列表。手机上折叠成一个抽屉，由顶部的按钮打开 -->
    <aside class="side" :class="{ open: listOpen }">
      <el-button type="primary" :icon="Plus" class="new" @click="newSession">
        新对话
      </el-button>

      <div class="side-label">历史会话</div>
      <el-empty v-if="sessions.length === 0" description="还没有会话" :image-size="50" />

      <div
        v-for="s in sessions"
        :key="s.id"
        class="sess"
        :class="{ active: s.id === currentId }"
        @click="openSession(s.id)"
      >
        <div class="sess-body">
          <div class="sess-title">{{ s.title }}</div>
          <div class="sess-time">{{ shortTime(s.updated_at) }}</div>
        </div>
        <el-button
          :icon="Delete"
          link
          class="sess-del"
          @click.stop="removeSession(s)"
        />
      </div>
    </aside>

    <section class="main">
      <div class="topbar">
        <el-button class="menu" text @click="listOpen = !listOpen">☰</el-button>
        <h1 class="title">问答</h1>
        <el-button :icon="Setting" link @click="$router.push('/ai/kb')">
          知识库
        </el-button>
      </div>

      <div ref="scroller" class="stream">
        <el-empty
          v-if="isEmpty"
          description="问点什么吧。比如「租房押金怎么要回来」——我会先去你的文章里找。"
          :image-size="70"
        />

        <div
          v-for="m in messages"
          :key="m.id"
          class="msg"
          :class="m.role"
        >
          <div class="bubble">
            <div class="text" v-html="renderText(m.content)" />
          </div>

          <!-- F13：知识库没匹配上时明确标注，不能让人以为这是自己文章里的结论 -->
          <div v-if="m.role === 'assistant' && !m.used_knowledge" class="note">
            <el-tag size="small" type="warning" effect="plain" disable-transitions>
              未引用你的文章
            </el-tag>
            <span class="note-text">知识库里没有找到相关内容，这是通用回答</span>
          </div>

          <div v-if="m.citations.length" class="cites">
            <span class="cites-label">引用：</span>
            <el-tag
              v-for="(c, i) in m.citations"
              :key="i"
              size="small"
              :type="scoreTag(c.score)"
              effect="plain"
              disable-transitions
            >
              《{{ c.title }}》 {{ c.score.toFixed(2) }}
            </el-tag>
          </div>
        </div>

        <!-- 正在流式生成的那一条 -->
        <div v-if="pending" class="msg assistant">
          <div class="bubble">
            <div class="text" v-html="renderText(pending.content)" />
            <span v-if="streaming" class="caret" />
          </div>

          <div v-if="!pending.used_knowledge" class="note">
            <el-tag size="small" type="warning" effect="plain" disable-transitions>
              未引用你的文章
            </el-tag>
            <span class="note-text">知识库里没有找到相关内容，这是通用回答</span>
          </div>

          <div v-if="pending.citations.length" class="cites">
            <span class="cites-label">引用：</span>
            <el-tag
              v-for="(c, i) in pending.citations"
              :key="i"
              size="small"
              :type="scoreTag(c.score)"
              effect="plain"
              disable-transitions
            >
              《{{ c.title }}》 {{ c.score.toFixed(2) }}
            </el-tag>
          </div>
        </div>
      </div>

      <div class="composer">
        <el-input
          v-model="input"
          type="textarea"
          :rows="2"
          resize="none"
          maxlength="2000"
          placeholder="问点什么…（Enter 发送，Shift+Enter 换行）"
          @keydown.enter.exact.prevent="send"
        />
        <el-button
          v-if="streaming"
          :icon="VideoPause"
          @click="stop"
        >
          停止
        </el-button>
        <el-button
          v-else
          type="primary"
          :icon="Promotion"
          :disabled="!canSend"
          @click="send"
        >
          发送
        </el-button>
      </div>
    </section>

    <div v-if="listOpen" class="backdrop" @click="listOpen = false" />
  </div>
</template>

<style scoped>
.chat {
  display: flex;
  gap: 16px;
  height: calc(100vh - 120px);
  min-height: 420px;
}

/* ---------- 左侧会话列表 ---------- */
.side {
  flex: none;
  width: 220px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  overflow-y: auto;
  padding-right: 4px;
}

.new {
  width: 100%;
}

.side-label {
  margin: 8px 0 2px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.sess {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 8px;
  border-radius: 6px;
  cursor: pointer;
}

.sess:hover {
  background: var(--el-fill-color-light);
}

.sess.active {
  background: var(--el-color-primary-light-9);
}

.sess-body {
  flex: 1;
  min-width: 0;
}

.sess-title {
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sess-time {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}

.sess-del {
  opacity: 0;
  flex: none;
}

.sess:hover .sess-del {
  opacity: 1;
}

/* ---------- 右侧对话区 ---------- */
.main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.topbar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.title {
  flex: 1;
  margin: 0;
  font-size: 20px;
}

.menu {
  display: none;
}

.stream {
  flex: 1;
  overflow-y: auto;
  padding: 4px 2px;
}

.msg {
  margin-bottom: 16px;
}

.msg.user {
  display: flex;
  justify-content: flex-end;
}

.msg.user .bubble {
  background: var(--el-color-primary);
  color: #fff;
  max-width: 80%;
}

.msg.assistant .bubble {
  background: var(--el-fill-color-light);
  max-width: 92%;
}

.bubble {
  display: inline-block;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 14px;
  line-height: 1.7;
}

.text {
  /* pre-wrap 让换行、缩进、空行都原样保留 ——
     没有引入 markdown 渲染器，格式全靠这个撑住 */
  white-space: pre-wrap;
  word-break: break-word;
}

.caret {
  display: inline-block;
  width: 6px;
  height: 15px;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: var(--el-color-primary);
  animation: blink 1s steps(2) infinite;
}

@keyframes blink {
  to {
    visibility: hidden;
  }
}

.note {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}

.note-text {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.cites {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}

.cites-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* ---------- 输入区 ---------- */
.composer {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}

.composer :deep(.el-textarea) {
  flex: 1;
}

.backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: 10;
}

@media (max-width: 768px) {
  .chat {
    height: calc(100vh - 90px);
  }

  .menu {
    display: inline-flex;
  }

  /* 会话列表变成抽屉，从左边滑出 */
  .side {
    position: fixed;
    top: 0;
    bottom: 0;
    left: 0;
    width: 240px;
    padding: 12px;
    background: var(--el-bg-color);
    z-index: 11;
    transform: translateX(-100%);
    transition: transform 0.2s;
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
  }

  .side.open {
    transform: translateX(0);
  }

  .sess-del {
    opacity: 1;
  }

  .msg.user .bubble {
    max-width: 88%;
  }
}
</style>
