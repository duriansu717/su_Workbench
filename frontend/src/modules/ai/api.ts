import api from '@/core/api'

/**
 * AI 问答模块的后端接口（AI1~AI7）。
 *
 * **AI8（提问）不在这里** —— 它要收 SSE 流，用不了 axios，
 * 单独放在 chat.ts 里。
 */

// ============================ 类型 ============================

export interface KbStatus {
  /** 当前可检索的文章数 */
  article_count: number
  /** 知识库里的分块数 */
  chunk_count: number
  embedding_model: string
  embedding_dim: number
  /** ★ 有多少块不是当前模型生成的。>0 就说明「换了模型但没重建」，
   *  那些块不会被检索用到，界面要把这件事明确提示出来。 */
  stale_chunk_count: number
  last_rebuilt_at: string | null
  last_error: string | null
}

export type RebuildStatus = 'idle' | 'running' | 'done' | 'failed' | 'interrupted'

export interface RebuildProgress {
  status: RebuildStatus
  total: number
  done: number
  failed: number
  last_error: string | null
  started_at: string | null
  finished_at: string | null
}

export interface Citation {
  article_id: number
  title: string
  /** 余弦相似度 0~1，也是调检索阈值时的依据 */
  score: number
  chunk_index: number
}

export interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  /** false 表示这次是 F13：知识库没匹配上，用的是通用回答 */
  used_knowledge: boolean
  citations: Citation[]
  created_at: string
}

export interface ChatSession {
  id: number
  title: string
  created_at: string
  updated_at: string
}

export interface SessionDetail extends ChatSession {
  messages: ChatMessage[]
}

// ============================ 接口 ============================

export const aiApi = {
  kb: {
    status: () => api.get<KbStatus>('/ai/kb/status'),

    /** 触发重建。**立即返回**，真正的活在后台跑，进度靠 progress() 轮询 */
    rebuild: () => api.post<RebuildProgress>('/ai/kb/rebuild'),

    progress: () => api.get<RebuildProgress>('/ai/kb/rebuild'),
  },

  sessions: {
    list: () => api.get<ChatSession[]>('/ai/sessions'),

    create: (title?: string) => api.post<ChatSession>('/ai/sessions', { title }),

    get: (id: number) => api.get<SessionDetail>(`/ai/sessions/${id}`),

    remove: (id: number) => api.delete(`/ai/sessions/${id}`),
  },
}

export default aiApi
