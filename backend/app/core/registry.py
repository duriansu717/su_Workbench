"""模块注册表 —— 整套架构的枢纽。

这是全项目唯一一个「新增模块时需要修改的已有文件」。新增一个模块，
只需要在下面 import 区加一行、在 MODULES 里加一项。

为什么用显式列表而不是自动扫描目录：自动扫描确实能少改一处，但它带来的魔法对
单人项目是负收益 —— 出问题时你没法从代码里一眼看出系统里到底有哪些模块。
"""

from app.core.module import ModuleInfo
from app.modules.ai.module import MODULE as ai
from app.modules.article.module import MODULE as article
from app.modules.plan.module import MODULE as plan

# ★★★ 新增模块，改这一行 ★★★
MODULES: tuple[ModuleInfo, ...] = (article, plan, ai)


def get_modules() -> list[ModuleInfo]:
    """按导航顺序返回全部模块。"""
    return sorted(MODULES, key=lambda m: m.order)


def get_module_names() -> list[str]:
    return [m.name for m in get_modules()]
