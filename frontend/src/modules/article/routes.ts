import type { RouteRecordRaw } from 'vue-router'

/**
 * 文章模块的前端路由。路径以模块名 article 开头。
 *
 * 页面一律用动态 import，这样只有访问到这个模块时才会加载它的代码 ——
 * 模块多了首屏也不会变慢。
 */
export const articleRoutes: RouteRecordRaw[] = [
  {
    path: 'article',
    name: 'article',
    component: () => import('./views/ArticleHomeView.vue'),
    meta: { title: '文章' },
  },
]
