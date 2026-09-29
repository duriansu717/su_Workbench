"""数据库连接与会话。

Base 是所有模块的表必须继承的基类。模块的表放在各自的 models.py 里，
但都继承同一个 Base —— 这样 Alembic 才能一次性看到全部表。
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

settings.ensure_directories()

engine = create_engine(
    settings.database_url,
    # SQLite 默认禁止跨线程复用同一个连接，而 FastAPI 的依赖注入会跨线程，必须关掉
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """全部模块的表都继承它。"""


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：每个请求一个数据库会话，请求结束自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
