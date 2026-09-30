"""AI 问答模块的接口（AI1~AI8）。

只做参数校验和调用 service，不写业务逻辑。
认证挂在 router 级别 —— 新增接口不可能忘记加保护。
"""

import json
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.modules.ai import service
from app.modules.ai.schemas import (
    ChatIn,
    KbStatusOut,
    RebuildOut,
    SessionCreate,
    SessionDetail,
    SessionOut,
)

router = APIRouter(dependencies=[Depends(get_current_user)])

DbSession = Annotated[Session, Depends(get_db)]


# ====================================================================
# 知识库（F11）
# ====================================================================


@router.get("/kb/status", response_model=KbStatusOut)
def kb_status(db: DbSession) -> KbStatusOut:
    """AI1 · 知识库状态。

    看两件事：库里有多少分块，以及**有多少块该重建了**（`stale_chunk_count`）。
    后者大于 0 说明换过 embedding 模型但没重建 —— 那些块不会被检索用到，
    必须显式报出来，否则用户只会觉得「检索结果莫名其妙」。
    """
    return service.kb_status(db)


@router.post(
    "/kb/rebuild", response_model=RebuildOut, status_code=status.HTTP_202_ACCEPTED
)
def rebuild_kb(db: DbSession, background: BackgroundTasks) -> RebuildOut:
    """AI2 · 触发重建索引。

    **立即返回，不等它跑完** —— 全量重建是分钟级的，HTTP 请求等不了这么久。
    真正的活在 BackgroundTasks 里跑，进度靠 AI3 轮询。

    没有用 Celery / Redis：那要额外装一个常驻服务，直接违背本项目
    「不装环境、省内存」的前提。代价是任务跑在进程内、重启就丢，
    所以服务启动时会把残留的 running 状态改成 interrupted（见 service）。
    """
    article_ids = service.begin_rebuild(db)
    background.add_task(service.run_rebuild, article_ids)
    return service.rebuild_progress(db)


@router.get("/kb/rebuild", response_model=RebuildOut)
def rebuild_progress(db: DbSession) -> RebuildOut:
    """AI3 · 查重建进度。前端在 status 为 running 时轮询这个接口。"""
    return service.rebuild_progress(db)


# ====================================================================
# 会话（AI4~AI7）
# ====================================================================


@router.get("/sessions", response_model=list[SessionOut])
def list_sessions(db: DbSession) -> list[SessionOut]:
    """AI4 · 会话列表，最近聊过的在前。不分页 —— 单人自用，数量有限。"""
    return service.list_sessions(db)


@router.post(
    "/sessions", response_model=SessionOut, status_code=status.HTTP_201_CREATED
)
def create_session(payload: SessionCreate, db: DbSession) -> SessionOut:
    """AI5 · 新建会话。标题不传就是「新对话」，前端之后可以拿首句提问补上。"""
    return service.create_session(db, payload.title)


@router.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(session_id: int, db: DbSession) -> SessionDetail:
    """AI6 · 会话详情，含全部消息（按时间正序）。"""
    return service.get_session(db, session_id)


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, db: DbSession) -> None:
    """AI7 · 删除会话。消息靠 ORM 级联一起删 —— 本项目没开外键校验，
    数据库不会替我们做这件事。"""
    service.delete_session(db, session_id)


# ====================================================================
# 提问（AI8 · F12 / F13）
# ====================================================================


def _sse(event: str, data: dict) -> str:
    """拼一个 SSE 帧。事件之间用空行分隔，`data` 后面那个换行不能少。"""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat")
async def chat(payload: ChatIn, db: DbSession) -> StreamingResponse:
    """AI8 · 提问，**SSE 流式返回**。

    **为什么流式**：模型生成一段几百字的回答要 5~15 秒。不流式就是盯着转圈干等，
    流式则是第一句出来就能开始读。

    事件顺序：`meta`（引用来源，**最先发**）→ 若干 `delta` → `done`。
    出错时是 `error`。

    会话是否存在在这里先用**请求的**会话校验，这样「会话不存在」是一个正常的
    404，而不是流里面的一条 error 事件。真正的生成过程在 service 里另开会话 ——
    流式响应期间，请求的依赖注入会话可能已经被关掉了。
    """
    service.ensure_session_exists(db, payload.session_id)

    async def event_stream():
        async for event, data in service.stream_answer(
            payload.session_id, payload.question
        ):
            yield _sse(event, data)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            # 关掉一切缓存。SSE 被缓存住的话，用户会收到上一次的回答。
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            # nginx 之类的反代默认会缓冲响应体，那会把流式效果完全毁掉
            # （变成攒够了才一次性吐出来）。这个头让它们别缓冲。
            "X-Accel-Buffering": "no",
        },
    )
