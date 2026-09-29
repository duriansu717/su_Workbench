"""骨架层自己的接口：健康检查 + 登录认证。

**认证为什么在 core 而不是 modules**：

它是基础设施，不是业务模块 —— 和后端的 security.py、deps.py 是一回事。
更硬的理由在前端：路由守卫住在 core，它必须能读到登录态；如果登录态属于某个
模块，core 就要反向依赖模块，违反架构设计第五章的依赖方向铁律。

这些接口由 main.py 直接挂载在 /api 下，不经过模块注册表 —— 因为它们本来就不是模块。
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import COOKIE_NAME, get_current_user
from app.core.models import User
from app.core.registry import get_modules
from app.core.schemas import LoginRequest, UserInfo
from app.core.security import create_access_token, verify_password

router = APIRouter()


# ============================ 健康检查 ============================


@router.get("/health", tags=["core"])
def health() -> dict:
    """健康检查。顺便返回当前加载了哪些模块，方便确认注册表生效。"""
    return {
        "status": "ok",
        "app": settings.app_name,
        "modules": [
            {"name": m.name, "title": m.title, "prefix": m.router_prefix}
            for m in get_modules()
        ],
    }


# ============================ 登录认证 ============================

auth = APIRouter(prefix="/auth", tags=["auth"])


def _authenticate(db: Session, username: str, password: str) -> User | None:
    """校验账号密码。成功返回 User，失败返回 None。

    认证本身在 core 里是自包含的：它只碰 user 一张表，不依赖任何业务模块。
    """
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


@auth.post("/login", response_model=UserInfo)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> UserInfo:
    """校验账号密码，成功后把 JWT 写进 httpOnly Cookie。

    放 httpOnly Cookie 而不是 localStorage：本项目要渲染富文本 HTML，
    万一出现 XSS，脚本读不到 httpOnly Cookie 里的 token。

    失败时统一返回"账号或密码不对"，不区分是账号不存在还是密码错 ——
    避免帮攻击者确认哪个账号是存在的。
    """
    user = _authenticate(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "账号或密码不对")

    response.set_cookie(
        key=COOKIE_NAME,
        value=create_access_token(user.username),
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,  # 前端 JS 读不到，防 XSS 窃取
        samesite="lax",  # 防 CSRF
        secure=settings.cookie_secure,
    )
    return UserInfo(username=user.username)


@auth.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    """退出登录：把 Cookie 删掉。

    服务端不维护会话状态，所以"退出"就是让浏览器丢掉那个 token。
    代价是签出去的 token 在过期前依然有效 —— 单人自用可以接受。
    """
    response.delete_cookie(COOKIE_NAME)


@auth.get("/me", response_model=UserInfo)
def me(username: str = Depends(get_current_user)) -> UserInfo:
    """返回当前登录的账号。前端用它判断"我是不是已经登录了"。"""
    return UserInfo(username=username)


router.include_router(auth)
