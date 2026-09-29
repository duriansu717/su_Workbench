import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

import AppLayout from './layout/AppLayout.vue'
import { getModules } from './registry'
import { useAuthStore } from './stores/auth'
import HomeView from './views/HomeView.vue'
import LoginView from './views/LoginView.vue'
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
    // 登录页**故意放在 AppLayout 外面** —— 没登录的时候不该看到侧边导航
    {
      path: '/login',
      name: 'login',
      component: LoginView,
      meta: { requiresAuth: false },
    },
    {
      path: '/',
      component: AppLayout,
      children: [
        { path: '', name: 'home', component: HomeView, meta: { title: '首页' } },
        ...moduleRoutes,
      ],
    },
    {
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: NotFoundView,
      meta: { requiresAuth: false },
    },
  ],
})

/**
 * 全局守卫。
 *
 * **默认要求登录**，只有显式标了 `meta.requiresAuth === false` 的页面例外。
 *
 * 为什么默认要登录而不是默认放行：以后新增页面时如果忘了标注，
 * 后果是多一层防护（打不开）而不是漏一个洞（被人看到）。错误方向要选安全的那个。
 */
router.beforeEach(async (to) => {
  const auth = useAuthStore()

  // 首次进入应用时问一次后端「我登录了吗」。
  // token 在 httpOnly Cookie 里，前端读不到，只能问。
  if (!auth.checked) {
    await auth.fetchMe()
  }

  if (to.meta.requiresAuth !== false && !auth.username) {
    // 记下原本想去的地址，登录后直接送过去
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  // 已经登录了就别再停在登录页
  if (to.name === 'login' && auth.username) {
    return { name: 'home' }
  }
})
