"""文章模块的自描述。

新增模块时，这个文件是模板 —— 只声明，不写逻辑。
"""

from app.core.module import ModuleInfo
from app.modules.article.router import router

MODULE = ModuleInfo(
    name="article",
    title="文章",
    icon="Document",
    router_prefix="/api/article",
    router=router,
    order=10,
    description="把生活里遇到的小问题记下来，用分类和标签整理",
)
