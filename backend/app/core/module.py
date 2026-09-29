"""模块契约：一个业务模块对自己的描述。

这是 core 与 modules 之间唯一的约定。每个模块在自己的 module.py 里导出一个
ModuleInfo 实例，声明它叫什么、挂在哪个路径下、在前端导航里显示成什么样子。

放在这里而不是 registry.py，是为了避免循环导入：

    modules/*/module.py  →  core/module.py
    core/registry.py     →  modules/*/module.py
"""

from dataclasses import dataclass

from fastapi import APIRouter


@dataclass(frozen=True)
class ModuleInfo:
    name: str
    """模块标识。同时作为前端路由段，如 "article"。"""

    title: str
    """前端导航里显示的中文名，如 "文章"。"""

    icon: str
    """前端图标名，对应 Element Plus 的图标组件，如 "Document"。"""

    router_prefix: str
    """后端接口前缀，如 "/api/article"。"""

    router: APIRouter
    """本模块的 APIRouter。由 main.py 按上面的前缀统一挂载。"""

    order: int = 100
    """前端导航排序，数字小的排在前面。"""

    description: str = ""
    """一句话说明，显示在首页模块卡片上。"""
