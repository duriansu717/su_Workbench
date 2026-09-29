"""文章模块的接口。

只做参数校验和调用 service，不写业务逻辑。

骨架阶段这里只有一条占位接口，用来验证「注册表 → 路由挂载 → 前端调通」
这条链路。真正的接口在「接口设计」阶段定义。
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
def ping() -> dict:
    """骨架占位接口，接入真实功能后删除。"""
    return {"module": "article", "ready": False, "message": "文章模块已注册并挂载"}
