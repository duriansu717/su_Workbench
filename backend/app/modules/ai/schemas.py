"""AI 问答模块的请求 / 响应模型。

字段命名、时间格式、错误码沿用文章模块（见接口设计文档第一章）。
"""

import json

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.schemas import UtcDatetime

# 问题长度上限。定在 2000 是留足余量 —— 真正的问题不会有这么长，
# 但没有上限的话，有人粘一整篇文章进来会直接烧掉一大笔 token。
QUESTION_MAX = 2000


class _OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ============================ 知识库 ============================


class KbStatusOut(BaseModel):
    """AI1 · 知识库状态。"""

    article_count: int
    chunk_count: int

    embedding_model: str
    embedding_dim: int

    # ★ 有多少块不是当前模型生成的。>0 就说明「换了模型但没重建」——
    #   这些块不会被检索用到（向量空间对不上），必须在这个接口里显式报出来，
    #   否则用户只会看到「检索结果莫名其妙」，完全想不到是模型换了。
    stale_chunk_count: int

    last_rebuilt_at: UtcDatetime | None = None
    last_error: str | None = None


class RebuildOut(BaseModel):
    """AI2 / AI3 · 重建进度。"""

    status: str
    total: int
    done: int
    failed: int
    last_error: str | None = None
    started_at: UtcDatetime | None = None
    finished_at: UtcDatetime | None = None


# ============================ 会话与消息 ============================


class Citation(BaseModel):
    """一条引用来源（F14 的引用溯源也靠它）。"""

    article_id: int
    title: str
    #: 余弦相似度，0~1。前端可以据此展示「相关度」，也是调阈值时的依据
    score: float
    chunk_index: int = 0


class MessageOut(_OrmModel):
    id: int
    role: str
    content: str
    used_knowledge: bool
    citations: list[Citation] = Field(default_factory=list)
    created_at: UtcDatetime

    @field_validator("citations", mode="before")
    @classmethod
    def _parse_citations(cls, value: object) -> object:
        """数据库里 `citations` 是一段 JSON 文本，接口要返回数组。

        **刻意把解析失败吞掉返回空数组**：历史消息里的引用来源坏掉，
        不该让整个会话打不开。宁可这一条少显示几个引用。
        """
        if value is None or value == "":
            return []
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return []
        return value


class SessionOut(_OrmModel):
    id: int
    title: str
    created_at: UtcDatetime
    updated_at: UtcDatetime


class SessionDetail(SessionOut):
    messages: list[MessageOut] = Field(default_factory=list)


class SessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ChatIn(BaseModel):
    session_id: int
    question: str = Field(min_length=1, max_length=QUESTION_MAX)
