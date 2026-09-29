"""计划模块的自描述。"""

from app.core.module import ModuleInfo
from app.modules.plan.router import router

MODULE = ModuleInfo(
    name="plan",
    title="计划",
    icon="Calendar",
    router_prefix="/api/plan",
    router=router,
    order=20,
    description="待办事项，以及按日 / 周 / 月查看的计划表",
)
