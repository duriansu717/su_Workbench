import { ChatDotRound } from '@element-plus/icons-vue'

import type { ModuleDef } from '@/core/module'
import { aiRoutes } from './routes'

export const aiModule: ModuleDef = {
  name: 'ai',
  title: '问答',
  icon: ChatDotRound,
  order: 30,
  description: '把文章变成知识库，用自己的话提问，拿自己的文章回答',
  routes: aiRoutes,
}
