"""文章模块的请求 / 响应模型。

与 models.py 分开：数据库结构是对内的，接口契约是对外的，两者不该直接等同，
否则改一次表结构就会意外改掉接口。

字段命名一律 snake_case，和数据库、Python 保持一致，**前端也直接用 snake_case**。
多一层驼峰转换就是多一个出错的地方，而且前后端字段名不一致时排查很费劲。
"""

from pydantic import BaseModel, ConfigDict, Field

from app.core.schemas import UtcDatetime


class _OrmModel(BaseModel):
    """能直接从 SQLAlchemy 对象构造的响应模型的基类。"""

    model_config = ConfigDict(from_attributes=True)


# ============================ 分类 ============================


class CategoryRef(_OrmModel):
    """嵌在文章里的分类引用，只有 id 和名字。"""

    id: int
    name: str


class CategoryOut(CategoryRef):
    sort_order: int
    article_count: int = 0


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    sort_order: int = 0


class CategoryUpdate(BaseModel):
    """两个字段都可选。只传要改的那个。"""

    name: str | None = Field(default=None, min_length=1, max_length=50)
    sort_order: int | None = None


# ============================ 标签 ============================


class TagRef(_OrmModel):
    id: int
    name: str


class TagOut(TagRef):
    article_count: int = 0


class TagCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class TagUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=50)


# ============================ 文章 ============================


class ArticleListItem(_OrmModel):
    """列表页的一项。**不含正文**。"""

    id: int
    title: str
    excerpt: str
    category: CategoryRef
    tags: list[TagRef]
    status: str
    created_at: UtcDatetime
    updated_at: UtcDatetime


class ArticleDetail(ArticleListItem):
    """详情页。比列表多一个正文，编辑器回填用。"""

    content_html: str
    deleted_at: UtcDatetime | None = None


class ArticleIn(BaseModel):
    """新建 / 更新文章的请求体。

    **故意没有 content_text** —— 纯文本一律由服务端从 content_html 抽取。

    如果让客户端传，就有了"只更新一个"的可能；而两者一旦不同步，
    搜索和 AI 检索会读到旧内容，**而且没有任何报错**。服务端抽取是唯一
    能保证同步的做法。详见接口设计文档 5.3 节。
    """

    title: str = Field(min_length=1, max_length=200)
    content_html: str = Field(min_length=1)
    category_id: int
    tag_ids: list[int] = Field(default_factory=list)


class ArticlePage(BaseModel):
    items: list[ArticleListItem]
    total: int
    page: int
    page_size: int


# ============================ 上传 ============================


class UploadOut(BaseModel):
    url: str
    size: int
