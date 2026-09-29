import { aiModule } from '@/modules/ai/module'
import { articleModule } from '@/modules/article/module'
import { planModule } from '@/modules/plan/module'

import type { ModuleDef } from './module'

/**
 * 前端模块注册表。
 *
 * 这是前端唯一一个「新增模块时需要修改的已有文件」。新增一个模块，
 * 只需要在下面的 import 区加一行、在 MODULES 里加一项。
 *
 * 为什么不用 import.meta.glob 自动扫描目录：自动扫描能少改这一处，
 * 但它带来的魔法对单人项目是负收益 —— 出问题时你没法从代码里一眼看出
 * 系统里到底有哪些模块。多写一行，换来随时可读的全貌。
 *
 * 关于 title / icon / order 在后端 module.py 里也声明了一份：这是有意的重复。
 * 前端导航不应该依赖后端接口返回才能渲染，否则后端一挂，界面就整个空了。
 */
// ★★★ 新增模块，改这一行 ★★★
export const MODULES: ModuleDef[] = [articleModule, planModule, aiModule]

/** 按导航顺序返回全部模块。 */
export function getModules(): ModuleDef[] {
  return [...MODULES].sort((a, b) => a.order - b.order)
}
