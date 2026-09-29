import { Document } from '@element-plus/icons-vue'

import type { ModuleDef } from '@/core/module'
import { articleRoutes } from './routes'

export const articleModule: ModuleDef = {
  name: 'article',
  title: '文章',
  icon: Document,
  order: 10,
  description: '把生活里遇到的小问题记下来，用分类和标签整理',
  routes: articleRoutes,
}
