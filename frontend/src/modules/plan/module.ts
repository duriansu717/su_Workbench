import { Calendar } from '@element-plus/icons-vue'

import type { ModuleDef } from '@/core/module'
import { planRoutes } from './routes'

export const planModule: ModuleDef = {
  name: 'plan',
  title: '计划',
  icon: Calendar,
  order: 20,
  description: '待办事项，以及按日 / 周 / 月查看的计划表',
  routes: planRoutes,
}
