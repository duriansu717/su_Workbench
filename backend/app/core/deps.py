"""通用依赖。

每个模块的受保护接口都用 get_current_user 做鉴权，所以它必须住在 core，
不能住在 auth 模块 —— 否则所有模块都得依赖 auth。
"""

from fastapi import Cookie, HTTPException, status

from app.core.security import decode_access_token

COOKIE_NAME = "access_token"


def get_current_user(access_token: str | None = Cookie(default=None)) -> str:
    """从 httpOnly Cookie 里取 token 并校验，返回用户名。

    放 httpOnly Cookie 而不是 localStorage：本项目要渲染富文本 HTML，
    万一出现 XSS，脚本读不到 httpOnly Cookie 里的 token。
    """
    if not access_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录")

    username = decode_access_token(access_token)
    if not username:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "登录已过期，请重新登录")

    return username
