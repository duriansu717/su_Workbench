"""Alembic 迁移环境。

改动过默认模板的地方有三处，都是必须的：

1. ★ 遍历模块注册表导入所有模型 —— 见下面那段注释，这是最容易踩的坑
2. 数据库地址从 app.core.config 读取，不写死在 alembic.ini 里
3. render_as_batch=True —— SQLite 特有的需要

新增模块时**这个文件不用改**，注册表改了模型就自动被发现。
"""

import importlib
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core import models as _core_models  # noqa: F401  导入全局表（user）
from app.core.config import settings
from app.core.database import Base
from app.core.registry import get_module_names

# ★★★ 这一句是整个文件里最重要的部分 ★★★
#
# SQLAlchemy 只有在模型类被 **import 过** 之后才知道它存在。
# 注册表里虽然写着有哪些模块，但那只是模块名，不会自动把 models.py 加载进来。
#
# 不写这个循环的后果：autogenerate 会生成一个**空的迁移脚本** ——
# 建表语句一条都没有，而你不会收到任何报错。你会对着那个空文件
# 反复怀疑自己模型是不是写错了，实际上只是没被导入。
#
# 这是架构设计文档第九章风险表里的第一条。
for _module_name in get_module_names():
    importlib.import_module(f"app.modules.{_module_name}.models")


config = context.config

# 数据库地址统一从应用配置读取，避免 alembic.ini 和 .env 两处配置不一致
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _common_options() -> dict:
    return {
        "target_metadata": target_metadata,
        # SQLite 不支持大部分 ALTER 语句（改列类型、加约束等）。
        # batch 模式让 Alembic 用「建新表 → 拷数据 → 换名」来实现变更。
        # 不加这个参数，以后任何一次修改表结构的迁移都会直接失败。
        "render_as_batch": True,
        # 让 autogenerate 能发现字段类型的变化，而不只是增删字段
        "compare_type": True,
    }


def run_migrations_offline() -> None:
    """离线模式：只生成 SQL，不连数据库。"""
    context.configure(
        url=settings.database_url,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_common_options(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线模式：连上数据库直接执行。"""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, **_common_options())
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
