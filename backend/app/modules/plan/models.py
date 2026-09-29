"""计划模块的表。

铁律一：这里只放本模块的表。计划模块完全独立，不引用任何其他模块。
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class Priority:
    """todo.priority 的取值。数字小的优先，这样能直接排序，不用写 CASE。"""

    HIGH = 1
    MEDIUM = 2
    LOW = 3


class Todo(TimestampMixin, Base):
    """一条待办事项。

    F10 的日 / 周 / 月三种视图用的是同一份数据，区别只是查询时对 planned_date
    取不同的范围（当天 / 本周一到周日 / 当月），所以是三张视图一张表。
    """

    __tablename__ = "todo"
    __table_args__ = (
        # 日 / 周 / 月视图的查询条件就是「未完成 + 日期在某范围内」
        Index("ix_todo_done_planned_date", "is_done", "planned_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ★ 这是**日历日期**，不是时间戳。
    # 「这件事计划在 10 月 1 日做」是日历上的一个格子，不是某个瞬间。
    # 按 UTC 存会让它平白偏移一天（中国是 UTC+8，10 月 1 日会变成 9 月 30 日 16:00）。
    # 所以这里用 Date 而不是 DateTime，且**绝不参与任何时区转换**。
    # 见 database.md 第一章。
    #
    # 为空表示还没安排到具体某天，相当于「收集箱」，不会出现在任何视图里。
    planned_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    priority: Mapped[int] = mapped_column(
        Integer, default=Priority.MEDIUM, nullable=False
    )
    is_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    done_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
