"""创建（或重置）工作台的登录账号。

用法（在 backend 目录下执行）：

    .venv/Scripts/python.exe -m scripts.create_user

为什么不用迁移脚本创建初始账号：**迁移脚本会进 git**，往里写死密码等于把密码
公开在仓库里，而且改了密码还得再写一个迁移。这里改成交互式输入，密码只存在于
内存和数据库的 bcrypt 哈希里。

脚本可以重复执行：账号已存在时会问你是否重置密码，用来救「密码忘了」的场景。
"""

import getpass
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.models import User
from app.core.security import hash_password

MIN_PASSWORD_LENGTH = 8


def _ask_password() -> str | None:
    """交互式读两次密码，不一致或太短返回 None。"""
    password = getpass.getpass("密码: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"密码至少 {MIN_PASSWORD_LENGTH} 位", file=sys.stderr)
        return None

    if password != getpass.getpass("再输一次: "):
        print("两次输入不一致", file=sys.stderr)
        return None

    return password


def main() -> int:
    username = input("账号: ").strip()
    if not username:
        print("账号不能为空", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.username == username))

        if existing is not None:
            answer = input(f"账号「{username}」已存在，重置它的密码吗？[y/N] ")
            if answer.strip().lower() != "y":
                print("已取消，没有做任何改动")
                return 0

            password = _ask_password()
            if password is None:
                return 1

            existing.password_hash = hash_password(password)
            db.commit()
            print(f"已重置「{username}」的密码")
            return 0

        password = _ask_password()
        if password is None:
            return 1

        db.add(User(username=username, password_hash=hash_password(password)))
        db.commit()
        print(f"已创建账号「{username}」")


    return 0


if __name__ == "__main__":
    raise SystemExit(main())
