"""骨架层的 Pydantic 模型。

只放跨模块共用的接口模型。业务模块的请求 / 响应模型放各自模块的 schemas.py。
"""

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class UserInfo(BaseModel):
    """返回给前端的用户信息。

    **故意只有 username** —— 不含 id、不含任何时间戳。
    登录接口的响应会出现在浏览器网络面板里，能不带的就不带。
    """

    username: str
