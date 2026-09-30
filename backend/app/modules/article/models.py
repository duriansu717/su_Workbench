"""文章模块的表。

**铁律一：这里只放本模块的表**，绝不在别的模块的模型上加字段，
也不在这里 import 别的模块的模型。
"""

from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Table,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, TimestampMixin

# 文章与标签的多对多中间表。
#
# 用 Table 而不是映射类：它是纯粹的关联表，没有额外字段。
# 附带一个重要好处 —— SQLAlchemy 会在删除任一端时自动清理关联行。
# 这一点在本项目里是必须的，因为我们没有启用数据库层的外键校验，
# 不会有人帮我们做 ON DELETE CASCADE（见 database.md 第七章）。
#
# 这里也**故意不写 ondelete="CASCADE"**：外键不校验，写了它也不会执行，
# 反而让人误以为级联生效了。级联统一交给 ORM 关系来做。
article_tag = Table(
    "article_tag",
    Base.metadata,
    Column("article_id", ForeignKey("article.id"), primary_key=True),
    Column("tag_id", ForeignKey("tag.id"), primary_key=True),
    # 联合主键已经覆盖了 article_id 开头的查询，
    # 反过来「按标签查文章」需要单独建索引
    Index("ix_article_tag_tag_id", "tag_id"),
)


class ArticleStatus:
    """article.status 的取值。

    不加数据库 CHECK 约束 —— SQLite 修改 CHECK 要整表重建，而这些值将来可能增加。
    合法性在应用层用这些常量 + Pydantic 校验保证。
    """

    DRAFT = "draft"
    PUBLISHED = "published"
    DELETED = "deleted"


# 列表页摘要截取多少字
EXCERPT_LENGTH = 120


class Category(TimestampMixin, Base):
    """文章的一级分类。没有 parent_id —— N6 已明确不做多级分类。"""

    __tablename__ = "category"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    articles: Mapped[list["Article"]] = relationship(back_populates="category")


class Tag(TimestampMixin, Base):
    """文章标签。一篇文章可以有多个，一个标签可以属于多篇文章。"""

    __tablename__ = "tag"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    articles: Mapped[list["Article"]] = relationship(
        secondary=article_tag, back_populates="tags"
    )


class Article(TimestampMixin, Base):
    """文章。本模块的核心表。"""

    __tablename__ = "article"
    __table_args__ = (
        # 列表页和搜索几乎总是「过滤掉已删除」+「按更新时间倒序」一起出现，
        # 建联合索引比两个单列索引更有效。
        # 左前缀也能单独服务「只按 status 过滤」的查询，所以不必再建 status 单列索引。
        Index("ix_article_status_updated_at", "status", "updated_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)

    # 富文本正文，给编辑器和页面渲染用。
    content_html: Mapped[str] = mapped_column(Text, nullable=False)

    # 纯文本副本，给搜索和 AI 切块用。
    # 富文本底层是 HTML，标签直接喂给 AI 检索会严重拉低效果。
    # **这两个字段必须在同一个 service 函数里一起写**，不要给调用方留"只更新一个"的可能。
    content_text: Mapped[str] = mapped_column(Text, nullable=False)

    # F17 自动摘要用，功能未做时为空
    summary: Mapped[str | None] = mapped_column(String(500), nullable=True)

    category_id: Mapped[int] = mapped_column(
        ForeignKey("category.id"), nullable=False, index=True
    )

    # 取值见 ArticleStatus。MVP 只用到 published 和 deleted，draft 留给以后
    status: Mapped[str] = mapped_column(
        String(20), default=ArticleStatus.PUBLISHED, nullable=False
    )

    # 移入回收站的时间，还原时清空
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    category: Mapped["Category"] = relationship(back_populates="articles")
    tags: Mapped[list["Tag"]] = relationship(
        secondary=article_tag, back_populates="articles"
    )

    @property
    def excerpt(self) -> str:
        """列表页展示的摘要。

        **故意不做成数据库字段**：摘要完全由 content_text 派生，存一份就多一处
        和正文不同步的可能 —— 而"两个字段不同步"正是这个项目一直在避免的事
        （content_html 和 content_text 必须在同一个函数里一起写，也是同一个原因）。
        """
        text = (self.content_text or "").strip()
        if len(text) <= EXCERPT_LENGTH:
            return text
        return text[:EXCERPT_LENGTH] + "…"
