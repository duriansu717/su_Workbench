import api from '@/core/api'

/** AI 问答模块的后端接口。骨架阶段只有一条占位接口。 */
export const aiApi = {
  ping: () => api.get<{ module: string; ready: boolean; message: string }>('/ai/ping'),
}
