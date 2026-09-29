import api from '@/core/api'

/**
 * 文章模块的后端接口。
 *
 * 只调用 /api/article/* —— 本模块不碰别的模块的接口，别的模块也不碰这里的。
 * 骨架阶段只有一条占位接口，真实接口在「接口设计」阶段补上。
 */
export const articleApi = {
  ping: () =>
    api.get<{ module: string; ready: boolean; message: string }>('/article/ping'),
}
