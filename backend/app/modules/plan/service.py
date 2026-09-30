"""计划模块的业务逻辑。

**公开函数即本模块对其他模块的接口。**

但计划模块目前既不需要别的模块的数据，也没有别的模块需要它的数据 ——
功能清单第四节的原话是「计划模块完全独立，不和其他模块产生任何关系」。
这是架构设计里"模块化竖切"最纯粹的一个例子。
"""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.modules.plan.models import Todo
from app.modules.plan.schemas import TodoCreate, TodoOut, TodoUpdate


def _get_or_404(db: Session, todo_id: int) -> Todo:
    todo = db.get(Todo, todo_id)
    if todo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "待办不存在")
    return todo


def list_todos(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    is_done: bool | None,
    unscheduled: bool,
) -> list[TodoOut]:
    """待办列表。

    日 / 周 / 月三种视图共用这一个查询，区别只是 from / to 不同 ——
    三张视图一份数据，不是三张表。
    """
    stmt = select(Todo)

    if unscheduled:
        # 收集箱：还没安排到具体某天的
        stmt = stmt.where(Todo.planned_date.is_(None))
    else:
        if date_from is not None:
            stmt = stmt.where(Todo.planned_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(Todo.planned_date <= date_to)

    if is_done is not None:
        stmt = stmt.where(Todo.is_done.is_(is_done))

    stmt = stmt.order_by(
        # ★ 让「没安排日期」的排到最后。
        # `planned_date IS NULL` 在 SQLite 里求值为 0 或 1，升序时 0（有日期）在前。
        # 直接 ORDER BY planned_date 的话 NULL 会排最前面（SQLite 里 NULL 最小），
        # 收集箱里的待办会挤在每一个日期视图的最上面。
        Todo.planned_date.is_(None),
        Todo.planned_date,
        Todo.priority,  # 1 高在前
        Todo.id,
    )

    return [TodoOut.model_validate(t) for t in db.scalars(stmt)]


def create_todo(db: Session, payload: TodoCreate) -> TodoOut:
    todo = Todo(
        title=payload.title,
        note=payload.note,
        planned_date=payload.planned_date,
        priority=payload.priority,
    )
    db.add(todo)
    db.commit()
    db.refresh(todo)
    return TodoOut.model_validate(todo)


def update_todo(db: Session, todo_id: int, payload: TodoUpdate) -> TodoOut:
    """部分更新。只改请求里真正出现过的字段。"""
    todo = _get_or_404(db, todo_id)

    # ★ exclude_unset 是 PATCH 语义的关键。
    # 它只返回「请求里真的传了的字段」，所以能区分：
    #   {}                      -> 什么都不改
    #   {"planned_date": null}  -> 取消安排，丢回收集箱
    # 不加这个参数，两者都会被当成"把 planned_date 设为 null"。
    changes = payload.model_dump(exclude_unset=True)

    if "title" in changes:
        todo.title = changes["title"]
    if "note" in changes:
        todo.note = changes["note"]
    if "planned_date" in changes:
        todo.planned_date = changes["planned_date"]
    if "priority" in changes:
        todo.priority = changes["priority"]

    # done_at 只由服务端维护 —— 请求模型里根本没有这个字段。
    # 勾选完成时记录时间，取消完成时清空。
    if "is_done" in changes:
        todo.is_done = changes["is_done"]
        todo.done_at = utcnow() if changes["is_done"] else None

    db.commit()
    db.refresh(todo)
    return TodoOut.model_validate(todo)


def delete_todo(db: Session, todo_id: int) -> None:
    """物理删除，没有回收站。

    回收站是功能清单 F5 对**文章**的要求，待办没有这条 —— 做完就打勾了，
    给它也留个回收站只会让本来就该清空的东西一直堆着。

    计划模块不引用任何其他模块的表，删起来没有连带影响。
    """
    todo = _get_or_404(db, todo_id)
    db.delete(todo)
    db.commit()
