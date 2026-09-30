import type { Citation } from './api'

/**
 * AI8 · 提问的流式客户端。
 *
 * ★ **用 fetch 手动解析 SSE，不用浏览器的 EventSource。**
 *   EventSource 有三个硬伤，正好全部命中这个场景：
 *     1. 只能发 GET —— 问题文本得塞进 query string，中文要编码还有长度上限
 *     2. 不能带自定义请求头
 *     3. 不能优雅取消（只能 close()，拿不到「中止」这个语义）
 *   fetch + ReadableStream 三样都能做。
 */

/** 服务端会依次发这些事件（见接口设计文档 4.3） */
export type ChatEvent =
  /** 检索一完成就发，**在回答开始生成之前** —— 引用来源能立刻显示出来 */
  | { type: 'meta'; used_knowledge: boolean; citations: Citation[] }
  /** 回答的一小段增量 */
  | { type: 'delta'; text: string }
  /** 结束，带上存库后的消息 id */
  | { type: 'done'; message_id: number }
  | { type: 'error'; detail: string }

export interface StreamHandlers {
  onMeta?: (used: boolean, citations: Citation[]) => void
  onDelta?: (text: string) => void
  onDone?: (messageId: number) => void
  onError?: (detail: string) => void
}

/** 解析一个 SSE 帧（形如 "event: meta\ndata: {...}"）。 */
function parseFrame(raw: string): ChatEvent | null {
  let event = 'message'
  const dataLines: string[] = []

  for (const line of raw.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }

  if (dataLines.length === 0) return null

  try {
    return { type: event, ...JSON.parse(dataLines.join('\n')) } as ChatEvent
  } catch {
    // 半截帧或者坏帧，跳过就好 —— 不值得为它中断整场回答
    return null
  }
}

export async function streamChat(
  sessionId: number,
  question: string,
  handlers: StreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  let resp: Response
  try {
    resp = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, question }),
      signal,
    })
  } catch (e) {
    // 用户主动取消不算错误
    if (signal?.aborted) return
    handlers.onError?.(`连不上服务：${e instanceof Error ? e.message : e}`)
    return
  }

  if (resp.status === 401) {
    // 和 core/api.ts 保持一致：直接跳登录页。
    // 这里不能 import 那边的处理函数 —— 会形成 core ← modules 的反向依赖。
    window.location.href = '/login'
    return
  }

  if (!resp.ok || !resp.body) {
    // 非流式的错误（422 / 404 / 500）走的是普通 JSON
    let detail = `HTTP ${resp.status}`
    try {
      const body = await resp.json()
      if (body?.detail) detail = String(body.detail)
    } catch {
      /* 不是 JSON 就算了，用状态码 */
    }
    handlers.onError?.(detail)
    return
  }

  const reader = resp.body.getReader()

  // ★ stream: true 是必须的。不加的话，一个中文字符被切在两个网络包里时，
  //   解码器会把两半各自当成非法字节，中文直接变成乱码。
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      // 服务端用 \n\n 分隔帧，但反代或中间层可能改成 \r\n\r\n
      buffer = buffer.replace(/\r\n/g, '\n')

      let cut = buffer.indexOf('\n\n')
      while (cut !== -1) {
        const frame = buffer.slice(0, cut)
        buffer = buffer.slice(cut + 2)

        const event = parseFrame(frame)
        if (event) {
          if (event.type === 'meta') handlers.onMeta?.(event.used_knowledge, event.citations)
          else if (event.type === 'delta') handlers.onDelta?.(event.text)
          else if (event.type === 'done') handlers.onDone?.(event.message_id)
          else if (event.type === 'error') handlers.onError?.(event.detail)
        }

        cut = buffer.indexOf('\n\n')
      }
    }
  } catch (e) {
    if (signal?.aborted) return
    handlers.onError?.(`读取回答时中断：${e instanceof Error ? e.message : e}`)
    return
  } finally {
    // 用户点了「停止」时，主动断开连接。
    // 服务端那边的生成器会收到取消，并把它已经生成的部分存进数据库
    // （见 ai/service.py 里 stream_answer 的 finally）。
    reader.cancel().catch(() => {})
  }
}
