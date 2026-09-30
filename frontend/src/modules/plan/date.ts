/**
 * 计划模块的日期工具。
 *
 * ★ 整个模块的日期都不走时区转换。
 *
 * `planned_date` 是**日历日期**（"2026-10-01"），不是时间戳 ——
 * 「这件事计划在 10 月 1 日做」是日历上的一个格子，不是某个瞬间。
 * 一旦让它经过 UTC，中国是 UTC+8，每条待办都会往前挪一天，而且不报任何错。
 *
 * 所以这里**绝不用 `toISOString()`** —— 它会先把本地时间转成 UTC 再格式化：
 *
 *     new Date(2026, 9, 1).toISOString().slice(0, 10)   // "2026-09-30"  ✗
 *     toYmd(new Date(2026, 9, 1))                       // "2026-10-01"  ✓
 */

export type CalendarView = 'day' | 'week' | 'month'

/** Date -> "2026-10-01"。用本地的年月日拼，不经过 UTC。 */
export function toYmd(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

/** "2026-10-01" -> Date。用本地时区解析，和 toYmd 对称。 */
export function fromYmd(ymd: string): Date {
  const [y, m, d] = ymd.split('-').map(Number)
  return new Date(y, m - 1, d)
}

/**
 * 某个视图下，锚点日期对应的查询区间。
 *
 * 返回 `[from, to]`，两端都含 —— 和接口的语义一致。
 *
 * **周从周一开始**（中国习惯）。这个约定放在前端而不是后端：
 * 一周从周几开始是展示层的习惯，后端只认 from / to，不该替前端猜。
 */
export function rangeOf(view: CalendarView, anchor: Date): [string, string] {
  if (view === 'day') {
    return [toYmd(anchor), toYmd(anchor)]
  }

  if (view === 'week') {
    // getDay() 周日是 0，转成「周一为 0」
    const offset = (anchor.getDay() + 6) % 7
    const monday = new Date(anchor)
    monday.setDate(anchor.getDate() - offset)
    const sunday = new Date(monday)
    sunday.setDate(monday.getDate() + 6)
    return [toYmd(monday), toYmd(sunday)]
  }

  // 注意这里用 new Date(y, m, 1) 而不是 setDate(1)：
  // 后者会就地改掉传入的 anchor，把它变成一个已修改的日期对象
  const first = new Date(anchor.getFullYear(), anchor.getMonth(), 1)
  // 下个月的第 0 天 = 这个月的最后一天
  const last = new Date(anchor.getFullYear(), anchor.getMonth() + 1, 0)
  return [toYmd(first), toYmd(last)]
}

/** 按视图前后翻页，返回新的锚点日期。 */
export function shift(view: CalendarView, anchor: Date, delta: number): Date {
  const next = new Date(anchor)
  if (view === 'day') next.setDate(anchor.getDate() + delta)
  else if (view === 'week') next.setDate(anchor.getDate() + delta * 7)
  else next.setMonth(anchor.getMonth() + delta)
  return next
}

const WEEKDAYS = ['周日', '周一', '周二', '周三', '周四', '周五', '周六']

/** 顶部显示的区间文案。 */
export function rangeLabel(view: CalendarView, anchor: Date): string {
  if (view === 'day') {
    return `${anchor.getFullYear()} 年 ${anchor.getMonth() + 1} 月 ${anchor.getDate()} 日 ${WEEKDAYS[anchor.getDay()]}`
  }

  if (view === 'week') {
    const [from, to] = rangeOf('week', anchor).map(fromYmd)
    const sameMonth = from.getMonth() === to.getMonth()
    const left = `${from.getMonth() + 1} 月 ${from.getDate()} 日`
    const right = sameMonth
      ? `${to.getDate()} 日`
      : `${to.getMonth() + 1} 月 ${to.getDate()} 日`
    return `${from.getFullYear()} 年 ${left} — ${right}`
  }

  return `${anchor.getFullYear()} 年 ${anchor.getMonth() + 1} 月`
}

/** 待办行上显示的日期短文案，如 "10-01"。 */
export function shortDate(ymd: string | null): string {
  if (!ymd) return ''
  const [, m, d] = ymd.split('-')
  return `${m}-${d}`
}

/** 今天是否是「今天」—— 用来给日期加标记。 */
export function isToday(ymd: string | null): boolean {
  return ymd === toYmd(new Date())
}
