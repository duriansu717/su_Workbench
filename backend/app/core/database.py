"""数据库连接与会话。

Base 是所有模块的表必须继承的基类。模块的表放在各自的 models.py 里，
但都继承同一个 Base —— 这样 Alembic 才能一次性看到全部表。
"""

from collections.abc import Generator
from datetime import datetime, timezone

from sqlalchemy import DateTime, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.core.config import settings

settings.ensure_directories()

engine = create_engine(
    settings.database_url,
    # SQLite 默认禁止跨线程复用同一个连接，而 FastAPI 的依赖注入会跨线程，必须关掉
    connect_args={"check_same_thread": False},
)

# 注意：这里**故意不设置 PRAGMA foreign_keys = ON**。
# 外键在模型里声明、在表结构里存在，但不启用校验。这是明确的设计取舍，
# 理由和代价见 docs/database/database.md 第七章第 1 条。
# 哪天想启用，在这里加一个事件监听器即可，不需要迁移。

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """全部模块的表都继承它。"""


def utcnow() -> datetime:
    """当前的 UTC 时间，**不带时区信息**。

    SQLite 不存储时区。如果写入带时区的值，读出来会变成不带时区的，
    两边一比较就抛 "can't compare offset-naive and offset-aware datetimes"。

    所以全项目统一约定：**库里存的永远是不带时区信息的 UTC 时间**，
    由前端负责转成本地时区显示。

    代码审查时看到 `datetime.now()` 没带参数，就是 bug —— 那存的是本地时间。
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TimestampMixin:
    """给表加上创建时间与更新时间。

    注意：`todo.planned_date` 不继承这套约定 —— 它是**日历日期**，
    不是时间戳，不做任何时区转换。见 database.md 第一章。
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求一个数据库会话，请求结束自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
