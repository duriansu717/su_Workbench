import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import AppLayout from './layout/AppLayout.vue'
import { getModules } from './registry'
import HomeView from './views/HomeView.vue'
import NotFoundView from './views/NotFoundView.vue'

/**
 * 模块路由从注册表收集，这里不手写任何模块的路径。
 *
 * 各模块在自己的 routes.ts 里对页面用动态 import（`() => import(...)`），
 * 这样模块多了也不会把首屏拖慢 —— 只有真正访问到的模块才会被加载。
 */
const moduleRoutes: RouteRecordRaw[] = getModules().flatMap((m) => m.routes)

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      component: AppLayout,
      children: [
        { path: '', name: 'home', component: HomeView, meta: { title: '首页' } },
        ...moduleRoutes,
      ],
    },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFoundView },
  ],
})
