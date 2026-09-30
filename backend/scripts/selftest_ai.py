"""AI 模块自测。**不需要 API Key，不联网，不碰数据库。**

    python -m scripts.selftest_ai

为什么单独写一份而不是用 pytest：这个项目从第一天起就定了「不装多余环境」，
pytest 虽小也是一层依赖。这份自测只用标准库，任何一台装了 Python 的机器上
`git clone` 下来就能跑，正好用来验证「切块 → 存储 → 检索」这条链路的正确性。

模型调用全程用 providers 里的 Fake 实现，所以不烧额度、不怕断网。
"""

import asyncio
import sys
import time

from app.modules.ai import chunking, service
from app.modules.ai.providers import FakeChat, FakeEmbedding

# Windows 控制台默认 GBK，打不出 ✔ / ✘ 和中文标点
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_passed = 0
_failed: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    global _passed
    if condition:
        _passed += 1
        print(f"  ✔ {name}")
    else:
        _failed.append(name)
        print(f"  ✘ {name}   {detail}")


def section(title: str) -> None:
    print()
    print("=" * 66)
    print(title)
    print("=" * 66)


# ====================================================================
# 一、切块
# ====================================================================

LONG = "\n\n".join(
    f"第{i}段。" + f"这是第{i}段的正文内容，用来把整篇文章撑到足够长以便触发切块。" * 4
    for i in range(1, 13)
)

NO_PUNCT = "甲" * 1300  # 完全没有标点，逼它硬切

SHORT = "就一句话。"


def test_chunking() -> None:
    section("一、切块 chunking.split_text")

    check("空文本返回空列表", chunking.split_text("") == [])
    check("纯空白返回空列表", chunking.split_text("   \n\n  ") == [])

    one = chunking.split_text(SHORT, size=500, overlap=100)
    check("短文本不切，整篇一块", one == [SHORT], f"得到 {len(one)} 块")

    chunks = chunking.split_text(LONG, size=500, overlap=100)
    print(f"     （{len(LONG)} 字 → {len(chunks)} 块）")
    check("长文本切成了多块", len(chunks) > 1, f"得到 {len(chunks)} 块")

    body = chunks[:-1]
    over = [i for i, c in enumerate(body) if len(c) > 500]
    check("除尾块外每块都不超过 size", not over, f"第 {over} 块超长")

    tail_ok = len(chunks[-1]) <= 500 + chunking.MIN_TAIL + 1
    check("尾块（可能已并入上一块）不超过 size+50", tail_ok, f"尾块 {len(chunks[-1])} 字")

    # 重叠：上一块的结尾应该能在下一块的开头附近找到
    overlapped = 0
    for i in range(len(chunks) - 1):
        prev_tail = chunks[i][-40:]
        if prev_tail and prev_tail in chunks[i + 1]:
            overlapped += 1
    check(
        "相邻块之间存在重叠",
        overlapped > 0,
        f"{len(chunks) - 1} 处接缝中有 {overlapped} 处重叠",
    )

    hard = chunking.split_text(NO_PUNCT, size=500, overlap=100)
    check("无标点超长文本能硬切", len(hard) >= 2, f"得到 {len(hard)} 块")
    check("硬切后每块仍不超过 size", all(len(c) <= 500 for c in hard))
    check("硬切不丢字", sum(len(c) for c in hard) >= len(NO_PUNCT) - 200)

    # 切块不能丢内容：所有块拼起来应该覆盖原文的绝大部分
    joined = "".join(chunks)
    check(
        "切块没有大面积丢内容",
        len(joined) >= len(LONG) * 0.9,
        f"原文 {len(LONG)} 字，块合计 {len(joined)} 字",
    )

    section("二、切块 chunking.chunk_article")

    titled = chunking.chunk_article("租房合同要注意什么", LONG, size=500, overlap=100)
    check("每块都带上了标题", all(t.startswith("租房合同要注意什么\n\n") for t in titled))
    check("带标题后块数不变", len(titled) == len(chunks))

    untitled = chunking.chunk_article("", SHORT, size=500, overlap=100)
    check("标题为空时不加前缀", untitled == [SHORT])

    check(
        "标题前后空白会被清掉",
        chunking.chunk_article("  标题  ", SHORT)[0].startswith("标题\n\n"),
    )


# ====================================================================
# 三、假 provider
# ====================================================================


def test_fake_providers() -> None:
    section("三、假 provider（离线测试的基础）")

    async def run() -> None:
        emb = FakeEmbedding(dim=64)

        vecs = await emb.embed(["租房的押金怎么退", "租房的押金怎么退", "今天天气不错"])
        check("向量维度正确", all(len(v) == 64 for v in vecs))
        check("同文本得到同向量（确定性）", vecs[0] == vecs[1])
        check("不同文本得到不同向量", vecs[0] != vecs[2])

        norm = sum(x * x for x in vecs[0]) ** 0.5
        check("向量已归一化", abs(norm - 1.0) < 1e-9, f"模长 {norm}")

        def cos(a, b):
            return sum(x * y for x, y in zip(a, b))

        close = cos(vecs[0], vecs[1])
        far = cos(vecs[0], vecs[2])
        check(
            "相似文本的余弦相似度高于无关文本",
            close > far,
            f"相同={close:.4f}  无关={far:.4f}",
        )

        check("空列表返回空列表", await emb.embed([]) == [])

        chat = FakeChat()
        pieces = [p async for p in chat.stream([{"role": "user", "content": "你好"}])]
        check("假对话能流出内容", len(pieces) > 1, f"得到 {len(pieces)} 段")
        check("假对话记录了收到的 messages", len(chat.calls) == 1)

    asyncio.run(run())


# ====================================================================
# 四、重建任务的看门狗
# ====================================================================


def test_rebuild_watchdog() -> None:
    section("四、重建任务的看门狗（防止永久 409）")

    original = service._running_since
    try:
        service._running_since = None
        check("没有任务在跑时返回 False", service._is_rebuilding() is False)

        service._running_since = time.monotonic()
        check("刚启动的任务算在跑", service._is_rebuilding() is True)

        service._running_since = time.monotonic() - 29 * 60
        check("跑了 29 分钟的仍算在跑（不会误杀长任务）", service._is_rebuilding() is True)

        service._running_since = time.monotonic() - 31 * 60
        check("超过 30 分钟没结束的算已经死了", service._is_rebuilding() is False)

        # 这一条是整个机制存在的理由：后台任务万一没跑起来，
        # 标志会永远留着，用户就会拿到永久性的 409。
        service._running_since = time.monotonic() - 24 * 3600
        check(
            "标志卡死一天之后能自己放行（不用重启服务）",
            service._is_rebuilding() is False,
        )
    finally:
        service._running_since = original


# ====================================================================


def main() -> int:
    print()
    print("AI 模块自测 —— 不联网、不需要 API Key、不碰数据库")

    test_chunking()
    test_fake_providers()
    test_rebuild_watchdog()

    print()
    print("=" * 66)
    if _failed:
        print(f"结果：{_passed} 通过，{len(_failed)} 失败")
        for name in _failed:
            print(f"  失败：{name}")
        return 1
    print(f"结果：全部 {_passed} 项通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
