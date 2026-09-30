import type { RouteRecordRaw } from 'vue-router'

/**
 * 文章模块的前端路由。路径都以模块名 article 开头。
 *
 * 页面一律用动态 import，这样只有访问到这个模块时才会加载它的代码 ——
 * 模块多了首屏也不会变慢。
 *
 * `:id(\\d+)` 约束只匹配数字，这样 `/article/new` 和 `/article/taxonomy`
 * 不会被当成文章 ID。虽然 vue-router 本来就会优先匹配静态路径，
 * 加上约束是双保险 —— 路由表顺序被人调换时也不会突然出错。
 */
export const articleRoutes: RouteRecordRaw[] = [
  {
    path: 'article',
    name: 'article',
    component: () => import('./views/ArticleListView.vue'),
    meta: { title: '文章' },
  },
  {
    path: 'article/new',
    name: 'article-new',
    component: () => import('./views/ArticleEditView.vue'),
    meta: { title: '新建文章' },
  },
  {
    path: 'article/taxonomy',
    name: 'article-taxonomy',
    component: () => import('./views/TaxonomyView.vue'),
    meta: { title: '分类与标签' },
  },
  {
    path: 'article/:id(\\d+)',
    name: 'article-detail',
    component: () => import('./views/ArticleDetailView.vue'),
    meta: { title: '文章详情' },
  },
  {
    path: 'article/:id(\\d+)/edit',
    name: 'article-edit',
    component: () => import('./views/ArticleEditView.vue'),
    meta: { title: '编辑文章' },
  },
]
