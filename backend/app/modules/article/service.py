"""文章模块的业务逻辑。

**铁律二：这个文件里公开的函数（不以 _ 开头）就是本模块对其他模块的接口。**

别的模块需要文章数据时，只能调这里的函数，不许 import 本模块的 models.py。
AI 模块将来会用到的：

    get_content(article_id)  —— 返回文章的标题与纯文本正文，供知识库切块

router.py 只做参数校验和调用这里，不写业务逻辑。
"""

import uuid
from datetime import datetime, timezone

import nh3
from bs4 import BeautifulSoup, NavigableString
from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.modules.article.models import (
    Article,
    ArticleStatus,
    Category,
    Tag,
    article_tag,
)
from app.modules.article.schemas import (
    ArticleDetail,
    ArticleIn,
    ArticlePage,
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    TagCreate,
    TagOut,
    TagUpdate,
    UploadOut,
)

# ============================ HTML 处理 ============================

# 富文本编辑器允许产生的标签。**白名单之外的一律丢弃** ——
# 黑名单思路永远追不上新出现的攻击手法。
ALLOWED_TAGS = {
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr", "blockquote", "pre", "code",
    "strong", "b", "em", "i", "u", "s",
    "ul", "ol", "li",
    "a", "img",
    "table", "thead", "tbody", "tr", "th", "td",
}

# 只允许这两个标签带属性，而且属性名也写死。
# 事件属性（onclick 等）不在白名单里，会被直接丢掉。
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
}

# 这些标签要连同**内容**一起删掉。<script> 只删标签不删内容的话，
# 里面的代码会变成正文的一部分泄漏出来。
CLEAN_CONTENT_TAGS = {"script", "style"}

# 块级标签：抽纯文本时前后要断行。
# 行内标签（strong / em / a / code）**绝不能断行** ——
# 否则"第一，<strong>押金</strong>条款"会变成三行，正文被切得稀碎。
BLOCK_TAGS = (
    "p", "div", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "blockquote", "pre", "tr", "br", "hr", "table", "ul", "ol",
)


def sanitize_html(raw_html: str) -> str:
    """白名单消毒。这是渲染富文本前唯一的防线。"""
    return nh3.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        clean_content_tags=CLEAN_CONTENT_TAGS,
        url_schemes={"http", "https", "mailto"},
        link_rel="noopener noreferrer",
    )


def html_to_text(clean_html: str) -> str:
    """从**已消毒**的 HTML 抽取纯文本。

    输入必须是 sanitize_html 的输出 —— 见 _prepare_content 里的顺序说明。
    """
    soup = BeautifulSoup(clean_html, "html.parser")

    for tag in soup.find_all(BLOCK_TAGS):
        tag.insert_before(NavigableString("\n"))
        tag.insert_after(NavigableString("\n"))

    lines = [line.strip() for line in soup.get_text("", strip=False).splitlines()]
    return "\n".join(line for line in lines if line)


def _prepare_content(content_html: str) -> tuple[str, str]:
    """消毒并抽取纯文本，返回 (干净的 HTML, 纯文本)。

    ★ **顺序不能换：先消毒，再抽纯文本。**

    反过来的话，本该被 CLEAN_CONTENT_TAGS 连内容一起删掉的 <script>，
    会先被抽进纯文本里 —— 而纯文本是要喂给 AI 的，等于把注入内容
    送进了知识库。这是接口设计文档第九章点名的那条。
    """
    clean = sanitize_html(content_html)
    return clean, html_to_text(clean)


# ============================ 分类 ============================


def _active_article_counts(db: Session) -> dict[int, int]:
    """每个分类下**未删除**的文章数，用于列表展示。"""
    rows = db.execute(
        select(Article.category_id, func.count(Article.id))
        .where(Article.status != ArticleStatus.DELETED)
        .group_by(Article.category_id)
    ).all()
    return {category_id: count for category_id, count in rows}


def list_categories(db: Session) -> list[CategoryOut]:
    counts = _active_article_counts(db)
    categories = db.scalars(
        select(Category).order_by(Category.sort_order, Category.id)
    ).all()
    return [
        CategoryOut(
            id=c.id,
            name=c.name,
            sort_order=c.sort_order,
            article_count=counts.get(c.id, 0),
        )
        for c in categories
    ]


def create_category(db: Session, payload: CategoryCreate) -> CategoryOut:
    if db.scalar(select(Category).where(Category.name == payload.name)):
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"分类「{payload.name}」已存在"
        )

    category = Category(name=payload.name, sort_order=payload.sort_order)
    db.add(category)
    db.commit()
    db.refresh(category)
    return CategoryOut(
        id=category.id,
        name=category.name,
        sort_order=category.sort_order,
        article_count=0,
    )


def update_category(db: Session, category_id: int, payload: CategoryUpdate) -> CategoryOut:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "分类不存在")

    if payload.name is not None and payload.name != category.name:
        clash = db.scalar(
            select(Category).where(
                Category.name == payload.name, Category.id != category_id
            )
        )
        if clash:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"分类「{payload.name}」已存在"
            )
        category.name = payload.name

    if payload.sort_order is not None:
        category.sort_order = payload.sort_order

    db.commit()
    db.refresh(category)
    return CategoryOut(
        id=category.id,
        name=category.name,
        sort_order=category.sort_order,
        article_count=_active_article_counts(db).get(category.id, 0),
    )


def delete_category(db: Session, category_id: int) -> None:
    """删除分类。删除前必须自己检查引用。

    ★ 数据库**没有启用外键校验**（见数据库设计第七章），删掉一个还有文章在用的
    分类，数据库不会拦住你 —— 那些文章会变成分类显示不出来的孤儿，而且全程不报错。

    统计的是**全部**文章（含回收站）。回收站里的文章一旦被还原，同样会变成孤儿，
    所以它们也算占用。
    """
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "分类不存在")

    total = db.scalar(
        select(func.count(Article.id)).where(Article.category_id == category_id)
    )
    if total:
        active = db.scalar(
            select(func.count(Article.id)).where(
                Article.category_id == category_id,
                Article.status != ArticleStatus.DELETED,
            )
        )
        trashed = total - active
        extra = f"（其中 {trashed} 篇在回收站）" if trashed else ""
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"分类「{category.name}」下还有 {total} 篇文章{extra}，不能删除",
        )

    db.delete(category)
    db.commit()


# ============================ 标签 ============================


def list_tags(db: Session) -> list[TagOut]:
    counts = dict(
        db.execute(
            select(article_tag.c.tag_id, func.count(article_tag.c.article_id))
            .join(Article, Article.id == article_tag.c.article_id)
            .where(Article.status != ArticleStatus.DELETED)
            .group_by(article_tag.c.tag_id)
        ).all()
    )
    tags = db.scalars(select(Tag).order_by(Tag.name)).all()
    return [
        TagOut(id=t.id, name=t.name, article_count=counts.get(t.id, 0)) for t in tags
    ]


def create_tag(db: Session, payload: TagCreate) -> TagOut:
    if db.scalar(select(Tag).where(Tag.name == payload.name)):
        raise HTTPException(status.HTTP_409_CONFLICT, f"标签「{payload.name}」已存在")

    tag = Tag(name=payload.name)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return TagOut(id=tag.id, name=tag.name, article_count=0)


def update_tag(db: Session, tag_id: int, payload: TagUpdate) -> TagOut:
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "标签不存在")

    if payload.name != tag.name:
        clash = db.scalar(
            select(Tag).where(Tag.name == payload.name, Tag.id != tag_id)
        )
        if clash:
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"标签「{payload.name}」已存在"
            )
        tag.name = payload.name

    db.commit()
    db.refresh(tag)
    return TagOut(id=tag.id, name=tag.name, article_count=0)


def delete_tag(db: Session, tag_id: int) -> None:
    """删除标签。

    和删除分类不同，**这里不需要检查引用** —— 删标签只是把它从所有文章上摘掉，
    article_tag 里的关联行由 SQLAlchemy 的 secondary 关系自动清理
    （见数据库设计 7.3 节）。
    """
    tag = db.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "标签不存在")
    db.delete(tag)
    db.commit()


# ============================ 文章 ============================


def _get_article_or_404(db: Session, article_id: int) -> Article:
    article = db.get(Article, article_id)
    if article is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文章不存在")
    return article


def _resolve_tags(db: Session, tag_ids: list[int]) -> list[Tag]:
    """按 ID 取标签。不存在的 ID **直接忽略**，不报错 ——
    前端可能持有已被别人删掉的标签 ID，为此报错很烦人。"""
    if not tag_ids:
        return []
    unique_ids = set(tag_ids)
    return list(db.scalars(select(Tag).where(Tag.id.in_(unique_ids))))


def _ensure_category_exists(db: Session, category_id: int) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "分类不存在")
    return category


def list_articles(
    db: Session,
    *,
    page: int,
    page_size: int,
    keyword: str | None,
    category_id: int | None,
    tag_id: int | None,
    article_status: str,
) -> ArticlePage:
    """文章列表：搜索 + 筛选 + 分页。排序固定按更新时间倒序（F8 的要求）。"""
    conditions = [Article.status == article_status]

    if category_id is not None:
        conditions.append(Article.category_id == category_id)

    if tag_id is not None:
        conditions.append(
            Article.id.in_(
                select(article_tag.c.article_id).where(article_tag.c.tag_id == tag_id)
            )
        )

    if keyword:
        # 前缀带通配符的 LIKE 用不上索引，全表扫描 ——
        # 当前数据量下几十毫秒，原文理由见数据库设计第六章第 6 条
        pattern = f"%{keyword}%"
        conditions.append(
            or_(Article.title.like(pattern), Article.content_text.like(pattern))
        )

    total = db.scalar(select(func.count(Article.id)).where(*conditions)) or 0

    items = db.scalars(
        select(Article)
        .where(*conditions)
        # 必须预加载 category 和 tags，否则 20 篇文章会打出 40 多次查询
        .options(selectinload(Article.category), selectinload(Article.tags))
        .order_by(Article.updated_at.desc(), Article.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return ArticlePage(items=list(items), total=total, page=page, page_size=page_size)


def get_article(db: Session, article_id: int) -> ArticleDetail:
    article = _get_article_or_404(db, article_id)
    return ArticleDetail.model_validate(article)


def create_article(db: Session, payload: ArticleIn) -> ArticleDetail:
    _ensure_category_exists(db, payload.category_id)

    content_html, content_text = _prepare_content(payload.content_html)

    article = Article(
        title=payload.title,
        content_html=content_html,
        content_text=content_text,
        category_id=payload.category_id,
        status=ArticleStatus.PUBLISHED,
    )
    article.tags = _resolve_tags(db, payload.tag_ids)

    db.add(article)
    db.commit()
    db.refresh(article)
    return ArticleDetail.model_validate(article)


def update_article(db: Session, article_id: int, payload: ArticleIn) -> ArticleDetail:
    article = _get_article_or_404(db, article_id)
    _ensure_category_exists(db, payload.category_id)

    # 重新消毒、重新抽纯文本。两个字段在同一个地方一起写 ——
    # 不能给调用方留"只更新一个"的可能
    content_html, content_text = _prepare_content(payload.content_html)

    article.title = payload.title
    article.content_html = content_html
    article.content_text = content_text
    article.category_id = payload.category_id
    article.tags = _resolve_tags(db, payload.tag_ids)

    db.commit()
    db.refresh(article)
    return ArticleDetail.model_validate(article)


def trash_article(db: Session, article_id: int) -> None:
    """移入回收站（软删除）。数据行保留，F5 要求能还原。"""
    article = _get_article_or_404(db, article_id)
    article.status = ArticleStatus.DELETED
    article.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()


def restore_article(db: Session, article_id: int) -> ArticleDetail:
    article = _get_article_or_404(db, article_id)
    if article.status != ArticleStatus.DELETED:
        raise HTTPException(status.HTTP_409_CONFLICT, "文章不在回收站里")

    article.status = ArticleStatus.PUBLISHED
    article.deleted_at = None
    db.commit()
    db.refresh(article)
    return ArticleDetail.model_validate(article)


def force_delete_article(db: Session, article_id: int) -> None:
    """彻底删除，**不可恢复**。

    标签关联由 SQLAlchemy 的 secondary 关系自动清理（数据库没启用外键校验，
    数据库不会做 ON DELETE CASCADE）。

    **本模块不负责清理 AI 模块的知识库分块** —— knowledge_chunk.article_id 是
    软引用，而反向调用 AI 模块会让 ai → article 的依赖成环。清理放在 AI 模块
    一侧：检索时过滤掉文章已不存在的分块，重建索引时删孤儿。详见接口设计 9 节。
    """
    article = _get_article_or_404(db, article_id)
    db.delete(article)
    db.commit()


# ============================ 供其他模块调用 ============================


def get_content(db: Session, article_id: int) -> dict | None:
    """给 AI 模块用的：返回文章的标题和**纯文本**正文。

    ★ 返回的是 content_text 而不是 content_html —— HTML 标签会污染语义匹配，
    这是数据库设计第六章第 1 条就把两个正文字段分开存的原因。

    文章不存在或已在回收站里，返回 None（而不是抛异常）——
    调用方是在批量处理的场景下用它，抛异常会让整个循环中断。
    """
    article = db.get(Article, article_id)
    if article is None or article.status == ArticleStatus.DELETED:
        return None
    return {
        "id": article.id,
        "title": article.title,
        "content_text": article.content_text,
        "category_id": article.category_id,
    }


def list_article_ids(db: Session) -> list[int]:
    """给 AI 模块用的：列出所有可检索的文章 ID（排除回收站里的）。"""
    return list(
        db.scalars(
            select(Article.id).where(Article.status != ArticleStatus.DELETED)
        )
    )


# ============================ 图片上传 ============================

ALLOWED_IMAGE_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


async def save_uploaded_image(file: UploadFile) -> UploadOut:
    """保存正文插图，返回可访问的相对 URL。

    ★ 文件名一律用 UUID 重新生成，**绝不使用客户端传来的文件名**。
    那个名字可能包含 `../`，直接拼进路径就能写到项目里的任何位置 ——
    上传一个叫 `../../app/main.py` 的"图片"就能覆盖源码。
    """
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"不支持的图片类型：{file.content_type or '未知'}",
        )

    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "图片不能超过 5 MB")

    extension = ALLOWED_IMAGE_TYPES[file.content_type]
    now = datetime.now(timezone.utc)
    sub_dir = f"{now.year:04d}-{now.month:02d}"

    target_dir = settings.upload_path / "images" / sub_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{extension}"
    (target_dir / filename).write_bytes(data)

    return UploadOut(url=f"/uploads/images/{sub_dir}/{filename}", size=len(data))
