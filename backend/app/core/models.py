"""全局表。

目前只有 user 一张表 —— 工作台只有一个账号，功能清单第四节把它标为
「全局，不归属任何模块」。

它放在 core 而不是 auth 模块，是为了让依赖方向保持干净：每个模块的接口都要靠
get_current_user 鉴权，如果这个依赖住在 auth 模块里，那 article、plan、ai
就全都要 import auth，多出一条本不该存在的依赖线。

具体字段在「数据库设计」阶段确定，这里先留空。
"""

from app.core.database import Base  # noqa: F401
