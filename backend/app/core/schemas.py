"""骨架层的 Pydantic 模型与公共类型。

只放跨模块共用的东西。业务模块的请求 / 响应模型放各自模块的 schemas.py。
"""

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, Field, PlainSerializer


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class UserInfo(BaseModel):
    """返回给前端的用户信息。

    **故意只有 username** —— 不含 id、不含任何时间戳。
    登录接口的响应会出现在浏览器网络面板里，能不带的就不带。
    """

    username: str


# ==================== 时间字段的序列化 ====================


def _ensure_utc(value: datetime) -> datetime:
    """把从库里读出来的「不带时区信息的 UTC 时间」补上时区标记。

    数据库里存的是 naive UTC（见数据库设计第一章）。补这一步是为了让序列化
    能输出带 `Z` 的字符串。
    """
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def _to_iso_z(value: datetime) -> str:
    return _ensure_utc(value).isoformat().replace("+00:00", "Z")


UtcDatetime = Annotated[
    datetime,
    BeforeValidator(_ensure_utc),
    PlainSerializer(_to_iso_z, return_type=str, when_used="json"),
]
"""接口返回给前端的时间字段，序列化后形如 `2026-09-29T15:30:00Z`。

**`Z` 后缀不能省。** 数据库里存的是不带时区信息的 UTC，如果接口原样返回
`"2026-09-29T15:30:00"`，前端 `new Date()` 会把它当成本地时间解析 ——
中国是 UTC+8，显示出来差 8 小时，**而且不报任何错**，只会让人以为是自己
的代码逻辑错了。

注意 `todo.planned_date` 不用这个类型：它是日历日期，不涉及时区。
"""
