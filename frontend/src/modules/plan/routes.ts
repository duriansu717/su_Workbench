import type { RouteRecordRaw } from 'vue-router'

/** 计划模块的前端路由。路径以模块名 plan 开头。 */
export const planRoutes: RouteRecordRaw[] = [
  {
    path: 'plan',
    name: 'plan',
    component: () => import('./views/PlanHomeView.vue'),
    meta: { title: '计划' },
  },
]
