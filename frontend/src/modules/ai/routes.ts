import type { RouteRecordRaw } from 'vue-router'

/** AI 问答模块的前端路由。路径以模块名 ai 开头。 */
export const aiRoutes: RouteRecordRaw[] = [
  {
    path: 'ai',
    name: 'ai',
    component: () => import('./views/AiHomeView.vue'),
    meta: { title: '问答' },
  },
]
