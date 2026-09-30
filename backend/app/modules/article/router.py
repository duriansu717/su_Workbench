"""文章模块的接口。

只做参数校验和调用 service，不写业务逻辑。

**认证挂在 router 级别**（下面的 dependencies），不是逐个接口标注 ——
这样以后新增接口不可能忘记加保护。默认拒绝，而不是默认放行。
"""

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.modules.article import service
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

router = APIRouter(dependencies=[Depends(get_current_user)])

DbSession = Annotated[Session, Depends(get_db)]


# ============================ 分类（F6） ============================


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: DbSession) -> list[CategoryOut]:
    """A1 · 分类列表。不分页 —— 分类是有限集合，一次全给。"""
    return service.list_categories(db)


@router.post("/categories", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, db: DbSession) -> CategoryOut:
    """A2 · 新建分类。重名返回 409。"""
    return service.create_category(db, payload)


@router.put("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int, payload: CategoryUpdate, db: DbSession
) -> CategoryOut:
    """A3 · 改名 / 排序。两个字段都可选，只传要改的。"""
    return service.update_category(db, category_id, payload)


@router.delete("/categories/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(category_id: int, db: DbSession) -> None:
    """A4 · 删除分类。**下面还有文章时会被拒绝** —— 详见 service 里的说明。"""
    service.delete_category(db, category_id)


# ============================ 标签（F7） ============================


@router.get("/tags", response_model=list[TagOut])
def list_tags(db: DbSession) -> list[TagOut]:
    """A5 · 标签列表。带每个标签下的文章数，前端展示用。"""
    return service.list_tags(db)


@router.post("/tags", response_model=TagOut, status_code=status.HTTP_201_CREATED)
def create_tag(payload: TagCreate, db: DbSession) -> TagOut:
    """A6 · 新建标签。"""
    return service.create_tag(db, payload)


@router.put("/tags/{tag_id}", response_model=TagOut)
def update_tag(tag_id: int, payload: TagUpdate, db: DbSession) -> TagOut:
    """A7 · 标签改名。"""
    return service.update_tag(db, tag_id, payload)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(tag_id: int, db: DbSession) -> None:
    """A8 · 删除标签。会把它从所有文章上摘掉，不需要先检查引用。"""
    service.delete_tag(db, tag_id)


# ============================ 文章（F2 / F4 / F5 / F8） ============================


@router.get("/articles", response_model=ArticlePage)
def list_articles(
    db: DbSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    keyword: Annotated[str | None, Query(max_length=100)] = None,
    category_id: int | None = None,
    tag_id: int | None = None,
    article_status: Annotated[
        str, Query(alias="status", pattern="^(published|deleted)$")
    ] = "published",
) -> ArticlePage:
    """A9 · 文章列表：搜索 + 筛选 + 分页。

    排序固定按更新时间倒序（F8 明确要求按时间排，不是按相关度），所以不开放排序参数。

    `status=deleted` 就是回收站列表，不另开接口。
    """
    return service.list_articles(
        db,
        page=page,
        page_size=page_size,
        keyword=keyword,
        category_id=category_id,
        tag_id=tag_id,
        article_status=article_status,
    )


@router.get("/articles/{article_id}", response_model=ArticleDetail)
def get_article(article_id: int, db: DbSession) -> ArticleDetail:
    """A10 · 文章详情。比列表多返回正文 HTML，编辑器回填用。"""
    return service.get_article(db, article_id)


@router.post("/articles", response_model=ArticleDetail, status_code=status.HTTP_201_CREATED)
def create_article(payload: ArticleIn, db: DbSession) -> ArticleDetail:
    """A11 · 新建文章。

    正文会经过白名单消毒，并自动抽取一份纯文本存起来（供搜索和 AI 用）。
    请求体里没有 content_text —— 那是服务端的事。
    """
    return service.create_article(db, payload)


@router.put("/articles/{article_id}", response_model=ArticleDetail)
def update_article(
    article_id: int, payload: ArticleIn, db: DbSession
) -> ArticleDetail:
    """A12 · 更新文章（全量）。会重新消毒并重新抽纯文本。"""
    return service.update_article(db, article_id, payload)


@router.delete("/articles/{article_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_article(article_id: int, db: DbSession) -> None:
    """A13 · 移入回收站（软删除）。数据行保留，可以还原。"""
    service.trash_article(db, article_id)


@router.post("/articles/{article_id}/restore", response_model=ArticleDetail)
def restore_article(article_id: int, db: DbSession) -> ArticleDetail:
    """A14 · 从回收站还原。文章本来就不在回收站时返回 409。"""
    return service.restore_article(db, article_id)


@router.delete("/articles/{article_id}/force", status_code=status.HTTP_204_NO_CONTENT)
def force_delete_article(article_id: int, db: DbSession) -> None:
    """A15 · 彻底删除，**不可恢复**。

    只删文章本身和它的标签关联，不碰 AI 模块的知识库 —— 原因见 service 里的说明。
    """
    service.force_delete_article(db, article_id)


# ============================ 图片上传（F3） ============================


@router.post(
    "/uploads/images", response_model=UploadOut, status_code=status.HTTP_201_CREATED
)
async def upload_image(file: Annotated[UploadFile, File()]) -> UploadOut:
    """A16 · 上传正文插图。

    只存文件不碰数据库 —— 图片什么时候真正和文章关联，取决于编辑器把返回的
    URL 插进正文 HTML，那一步在保存文章时自然完成。
    """
    return await service.save_uploaded_image(file)
