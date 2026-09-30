"""计划模块的接口。

只做参数校验和调用 service，不写业务逻辑。
认证挂在 router 级别 —— 新增接口不可能忘记加保护。
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.modules.plan import service
from app.modules.plan.schemas import TodoCreate, TodoOut, TodoUpdate

router = APIRouter(dependencies=[Depends(get_current_user)])

DbSession = Annotated[Session, Depends(get_db)]


@router.get("/todos", response_model=list[TodoOut])
def list_todos(
    db: DbSession,
    # `from` 是 Python 关键字，不能当参数名，所以用别名映射过去。
    # 对外的接口参数名仍然是 from / to。
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    is_done: bool | None = None,
    unscheduled: bool = False,
) -> list[TodoOut]:
    """P1 · 待办列表。

    日 / 周 / 月三种视图**共用这一个接口**，区别只是前端传的 from / to 不同：

    | 视图 | from / to |
    |------|-----------|
    | 日   | 当天 / 当天 |
    | 周   | 本周一 / 本周日 |
    | 月   | 当月 1 日 / 当月最后一天 |

    周的起始（周一还是周日）由前端决定，后端不猜 —— 那是展示层的约定。
    """
    return service.list_todos(
        db,
        date_from=date_from,
        date_to=date_to,
        is_done=is_done,
        unscheduled=unscheduled,
    )


@router.post("/todos", response_model=TodoOut, status_code=status.HTTP_201_CREATED)
def create_todo(payload: TodoCreate, db: DbSession) -> TodoOut:
    """P2 · 新建待办。不传 planned_date 就是进收集箱，等以后再安排。"""
    return service.create_todo(db, payload)


@router.patch("/todos/{todo_id}", response_model=TodoOut)
def update_todo(todo_id: int, payload: TodoUpdate, db: DbSession) -> TodoOut:
    """P3 · 部分更新。所有字段可选，只改传上来的。

    用 PATCH 而不是 PUT，是因为"勾选完成"只改一个字段 —— 用全量更新的话，
    前端得先把整条待办读出来再原样提交回去，多一次往返，
    而且中间读漏一个字段就会被静默覆盖。

    `done_at` 由服务端根据 is_done 自动维护，请求体里没有这个字段。
    """
    return service.update_todo(db, todo_id, payload)


@router.delete("/todos/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_todo(todo_id: int, db: DbSession) -> None:
    """P4 · 删除待办。**物理删除，没有回收站** —— 理由见 service 里的说明。"""
    service.delete_todo(db, todo_id)
