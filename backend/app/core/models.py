"""全局表。

目前只有 user 一张 —— 工作台只有一个账号，功能清单第四节把它标为
「全局，不归属任何模块」。

放在 core 而不是 auth 模块的原因见架构设计 3.1 节：每个模块的接口都要靠
get_current_user 鉴权，如果它住在 auth 模块里，其他模块就都得依赖 auth。
"""

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, TimestampMixin


class User(TimestampMixin, Base):
    """工作台的唯一使用者。系统里只会有一条记录。"""

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # bcrypt 哈希，绝不存明文。bcrypt 输出固定 60 字符，留 100 是余量。
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
