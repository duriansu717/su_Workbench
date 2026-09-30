import api from '@/core/api'

/**
 * 计划模块的后端接口（P1~P4）。
 *
 * **日期参数一律用 date.ts 的 `toYmd()` 生成字符串**，不要用 `toISOString()`
 * —— 后者会先把本地时间转成 UTC，中国时区下 10 月 1 日会变成 9 月 30 日。
 * 详见 date.ts 顶部的说明。
 */

// ============================ 类型 ============================

export const PRIORITY = { HIGH: 1, MEDIUM: 2, LOW: 3 } as const

export const PRIORITY_LABEL: Record<number, string> = {
  [PRIORITY.HIGH]: '高',
  [PRIORITY.MEDIUM]: '中',
  [PRIORITY.LOW]: '低',
}

/** Element Plus 的 tag type */
export const PRIORITY_TAG: Record<number, 'danger' | 'warning' | 'info'> = {
  [PRIORITY.HIGH]: 'danger',
  [PRIORITY.MEDIUM]: 'warning',
  [PRIORITY.LOW]: 'info',
}

export interface Todo {
  id: number
  title: string
  note: string | null
  /** "2026-10-01" —— 日历日期，不带时间也不带 Z。null 表示还没安排 */
  planned_date: string | null
  /** 1 高 / 2 中 / 3 低 */
  priority: number
  is_done: boolean
  /** 完成时间，带 Z。由服务端维护，客户端设不了 */
  done_at: string | null
  created_at: string
  updated_at: string
}

export interface TodoQuery {
  /** 计划日期 >= （含），"2026-10-01" 格式 */
  from?: string
  /** 计划日期 <= （含） */
  to?: string
  is_done?: boolean
  /** true 时只看没有计划日期的（收集箱），并忽略 from / to */
  unscheduled?: boolean
}

export interface TodoInput {
  title: string
  note?: string | null
  planned_date?: string | null
  priority?: number
}

/** PATCH 的部分更新。只传要改的字段。 */
export type TodoPatch = Partial<TodoInput> & { is_done?: boolean }

// ============================ 接口 ============================

export const planApi = {
  todos: {
    /**
     * 待办列表。
     *
     * 日 / 周 / 月三种视图**共用这一个查询**，区别只是 from / to 不同 ——
     * 用 date.ts 的 `rangeOf()` 算区间。
     */
    list: (params: TodoQuery = {}) => api.get<Todo[]>('/plan/todos', { params }),

    create: (payload: TodoInput) => api.post<Todo>('/plan/todos', payload),

    /** 部分更新。勾选完成也是走这里（传 is_done），done_at 由服务端维护 */
    update: (id: number, payload: TodoPatch) => api.patch<Todo>(`/plan/todos/${id}`, payload),

    /** 物理删除，没有回收站 */
    remove: (id: number) => api.delete(`/plan/todos/${id}`),
  },
}

export default planApi
