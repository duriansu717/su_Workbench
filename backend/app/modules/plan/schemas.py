"""计划模块的请求 / 响应模型。

字段命名和错误码约定沿用文章模块（见接口设计文档）。
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.core.schemas import UtcDatetime
from app.modules.plan.models import Priority


class _OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TodoOut(_OrmModel):
    id: int
    title: str
    note: str | None = None

    # ★ 这是**日历日期**，不是时间戳。
    # Pydantic 的 date 类型序列化出来就是 "2026-10-01" —— 不带时间、不带 Z、
    # 不做时区转换，正是我们要的形状。**别手滑改成 datetime**：
    # 日 / 周 / 月三种视图全在拿这个字段做范围查询，一旦引入时区，
    # 中国时区下每条待办都会往前挪一天，而且不报任何错。
    planned_date: date | None = None

    priority: int
    is_done: bool
    done_at: UtcDatetime | None = None
    created_at: UtcDatetime
    updated_at: UtcDatetime


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    note: str | None = None
    planned_date: date | None = None
    priority: int = Field(default=Priority.MEDIUM, ge=1, le=3)


class TodoUpdate(BaseModel):
    """部分更新：所有字段可选，只改传上来的。

    ★ **故意没有 done_at**。它由服务端根据 is_done 自动维护，
    放进请求体就等于允许客户端伪造完成时间。

    注意区分「没传 planned_date」和「显式传 planned_date=null」——
    前者是不改，后者是取消安排（把待办丢回收集箱）。
    service 里靠 `model_dump(exclude_unset=True)` 区分这两者。
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    note: str | None = None
    planned_date: date | None = None
    priority: int | None = Field(default=None, ge=1, le=3)
    is_done: bool | None = None
