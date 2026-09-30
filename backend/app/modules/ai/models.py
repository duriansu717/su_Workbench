"""AI 问答模块的表。

铁律一：这里只放本模块的表。

与文章模块的关系是**单向软引用**：本模块存文章 ID，但不建外键、不 import
文章模块的模型。需要正文时调用文章模块 service.py 暴露的函数。
详见架构设计第七章。
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin, utcnow


class MessageRole:
    """chat_message.role 的取值。"""

    USER = "user"
    ASSISTANT = "assistant"


class RebuildStatus:
    """kb_rebuild_state.status 的取值。"""

    IDLE = "idle"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    # 服务重启时，还停在 RUNNING 的记录会被改成这个 ——
    # 任务跑在进程内，进程没了任务就没了，必须留下痕迹，
    # 否则界面会永远显示「正在重建」。
    INTERRUPTED = "interrupted"


class KnowledgeChunk(Base):
    """知识库分块：文章切块后的文本与向量。

    只继承 Base 不继承 TimestampMixin —— 这张表只有 updated_at，
    因为「这块是何时创建的」没有意义，重要的是「何时重新生成的」。
    """

    __tablename__ = "knowledge_chunk"
    __table_args__ = (
        UniqueConstraint(
            "article_id", "chunk_index", name="uq_knowledge_chunk_article_index"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # 软引用：存文章 ID 但**不建外键**。
    # 架构设计第五章铁律一要求模块不碰对方的表；建了外键两张表就在数据库
    # 层面绑死了，将来想拆模块会成为障碍。见 database.md 第六章第 3 条。
    #
    # 代价：删文章时不会自动清理这里的分块，需要文章模块的删除逻辑主动调用
    # 本模块 service 暴露的清理函数。
    article_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # 切块后的纯文本。**来自 article.content_text，绝不来自 content_html** ——
    # HTML 标签会污染语义匹配。见 database.md 第六章第 1 条。
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)

    # 向量以 float32 原始字节存储。维度记在 vector_dim 里，
    # 对维度完全透明 —— 换 embedding 模型时不需要改表结构。
    # 存取无损，实测数据见技术栈文档 3.7 节。
    vector: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # ★ 下面两个字段是给「换 embedding 模型」准备的。
    # 换模型后旧向量和新问题不在同一个向量空间里，混用会检索出完全无关的内容，
    # **而且不会报错**，只会让回答变得莫名其妙。
    # 有了这两个字段，重建索引时能精确识别哪些块是旧模型生成的。
    vector_dim: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(100), nullable=False)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class ChatSession(TimestampMixin, Base):
    """一次连续的对话。"""

    __tablename__ = "chat_session"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    # ORM 级联：删会话时自动删掉它的消息。
    # 不能指望数据库的 ON DELETE CASCADE —— 本项目没启用外键校验，数据库不会做这件事。
    #
    # order_by 是必须的：不写的话消息顺序由数据库的返回顺序决定，
    # 平时恰好是主键序，看起来没问题，一旦有并发写入或者换了数据库实现
    # 就会乱序 —— 而且只在界面上表现为「对话顺序错乱」，很难往这里想。
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.id",
    )


class ChatMessage(TimestampMixin, Base):
    """会话里的单条消息。"""

    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_session.id"), nullable=False, index=True
    )

    # 取值见 MessageRole
    role: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 是否引用了知识库。F13 要求知识库无匹配时标注「未引用你的文章」，靠这个字段。
    used_knowledge: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    # 引用来源的 JSON 数组：
    #   [{"article_id": 3, "title": "租房合同要注意什么", "score": 0.87}]
    #
    # 把文章标题也冗余存进来，好处是**文章被删掉后，历史回答的引用来源仍然显示得出来**。
    # 用 JSON 而不是独立表的理由见 database.md 第六章第 4 条。
    citations: Mapped[str | None] = mapped_column(Text, nullable=True)

    session: Mapped["ChatSession"] = relationship(back_populates="messages")


class KbRebuildState(Base):
    """重建索引的进度。**单行表**，固定 id=1，每次重建覆盖它。

    为什么进度要落库而不是放内存：

    1. 重建是**分钟级**的，用户不会盯着进度条不动 —— 关掉页面去干别的、
       回来后进度得还在。放内存里页面一刷新就归零了。
    2. 重建任务用的是 FastAPI 的 BackgroundTasks，**跑在进程内，重启就没了**。
       如果状态只在内存里，重启后进程里什么都没有，界面会永远卡在
       「正在重建」而没有任何办法恢复。落库之后启动时还能把它改成
       INTERRUPTED，至少能说清楚发生了什么。

    为什么不建「重建历史表」记录每一次重建：单人自用，重建是手动触发的，
    「上上次花了多久」没有任何决策价值。单行表足够，也少一张会不断增长的表。
    """

    __tablename__ = "kb_rebuild_state"

    # 固定 1。单行表，读的时候 db.get(KbRebuildState, 1)。
    id: Mapped[int] = mapped_column(primary_key=True, default=1)

    status: Mapped[str] = mapped_column(
        String(20), default=RebuildStatus.IDLE, nullable=False
    )

    total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # 失败的篇数。单篇失败不会中断整个任务（理由见 service.rebuild_index）
    failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 最近一条错误信息。成功时为 None。
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # 上次**成功**重建的时间。和 finished_at 分开记：一次失败的重建也会写
    # finished_at，但那不该被当成「知识库最近一次更新」。
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
