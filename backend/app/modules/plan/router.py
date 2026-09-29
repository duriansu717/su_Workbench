"""计划模块的接口。骨架阶段只有一条占位接口。"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/ping")
def ping() -> dict:
    """骨架占位接口，接入真实功能后删除。"""
    return {"module": "plan", "ready": False, "message": "计划模块已注册并挂载"}
