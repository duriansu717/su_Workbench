import type { Component } from 'vue'
import type { RouteRecordRaw } from 'vue-router'

/**
 * 一个业务模块对前端外壳的自描述。
 *
 * 与后端 app/core/module.py 里的 ModuleInfo 是同一份契约的前后端两半：
 * 后端那半管路由挂载，这半管导航渲染和前端路由。
 */
export interface ModuleDef {
  /** 模块标识。同时作为路由段（/article）和后端接口前缀（/api/article）。 */
  name: string

  /** 导航里显示的名字。 */
  title: string

  /** 导航图标。直接存组件而不是名字，这样只有用到的图标会被打进包。 */
  icon: Component

  /** 导航排序，数字小的排在前面。 */
  order: number

  /** 首页模块卡片上的一句话说明。 */
  description: string

  /** 本模块的前端路由，路径以 name 开头。 */
  routes: RouteRecordRaw[]
}
