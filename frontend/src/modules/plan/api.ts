import api from '@/core/api'

/** 计划模块的后端接口。骨架阶段只有一条占位接口。 */
export const planApi = {
  ping: () => api.get<{ module: string; ready: boolean; message: string }>('/plan/ping'),
}
