"""AI 问答模块的自描述。"""

from app.core.module import ModuleInfo
from app.modules.ai.router import router

MODULE = ModuleInfo(
    name="ai",
    title="问答",
    icon="ChatDotRound",
    router_prefix="/api/ai",
    router=router,
    order=30,
    description="把文章变成知识库，用自己的话提问，拿自己的文章回答",
)
