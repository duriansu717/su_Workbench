"""模型调用的封装。

**全项目唯一碰模型 API 的地方。** 业务代码（service.py）只依赖这里定义的
Protocol，不认识 openai SDK，也不认识「百炼」两个字 —— 换供应商只改 .env 里的
AI_BASE_URL 和两个模型名，service 一行不动。

另外提供了 **Fake 实现**：切块、存储、检索、重建进度、界面这些逻辑全都可以
用一个不联网的假 provider 跑通并测试，既不烧额度也不怕断网。
"""

import hashlib
import math
import zlib
from collections.abc import AsyncIterator, Sequence
from typing import Any, Protocol

from app.core.config import settings

# 百炼的 embedding 接口**单次最多 10 条**文本，超过直接被拒。
# 这个数字是供应商的硬约束，不是可调参数，所以写在代码里而不是 .env 里。
EMBED_BATCH = 10


class ModelError(Exception):
    """模型调用失败。

    message 是一句**可以直接显示给用户的中文说明**，不是堆栈。
    调用方（service / router）拿到后原样往外抛即可。
    """


# ============================ 抽象接口 ============================


class EmbeddingProvider(Protocol):
    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """把一批文本转向量。**返回顺序与入参一一对应。**

        批量上限、重试、分批都在实现里处理掉，调用方不用管。
        """
        ...


class ChatProvider(Protocol):
    def stream(self, messages: Sequence[dict[str, str]]) -> AsyncIterator[str]:
        """流式生成回答，逐段吐出**纯文本增量**。

        实现里必须过滤掉思考内容（见 DashScopeChat 里的说明），
        调用方拿到的一定是要显示给用户的部分。
        """
        ...


# ============================ 真实实现 ============================


def _explain(exc: Exception) -> str:
    """把 SDK 抛出的异常翻译成一句人话。

    刻意用 getattr 取 status_code 而不是 import 一堆异常类 —— 依赖 openai 的
    异常层次结构会让这段代码随 SDK 版本变脆，而它本来只需要一个数字。
    """
    status = getattr(exc, "status_code", None)
    name = type(exc).__name__

    if status == 401:
        return (
            "API Key 无效或已过期。去阿里云百炼控制台确认后，"
            "更新 backend/.env 里的 DASHSCOPE_API_KEY"
        )
    if status == 404:
        return (
            "模型名不存在。百炼会定期下线旧模型 —— "
            "去 backend/.env 换一个新的模型名即可，不用改代码"
        )
    if status == 429:
        return "被限流或免费额度已用完。稍后重试，或去控制台查看用量"
    if status == 400:
        return f"请求被拒绝（HTTP 400）：{exc}"
    if isinstance(status, int) and status >= 500:
        return f"模型服务端错误（HTTP {status}），通常稍后重试即可"
    if "Timeout" in name:
        return "请求模型超时。检查网络后重试"
    if "Connection" in name:
        return "连不上模型服务。检查网络是否正常"
    return f"{name}: {exc}"


def _client() -> Any:
    """懒加载并复用 AsyncOpenAI 客户端。

    每次调用都新建一个的话，连接池会一直重建，白费握手开销。
    """
    global _CLIENT
    if _CLIENT is None:
        from openai import AsyncOpenAI

        _CLIENT = AsyncOpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.ai_base_url,
        )
    return _CLIENT


_CLIENT: Any = None


class DashScopeEmbedding:
    """走 OpenAI 兼容接口的向量化。百炼 / 硅基流动 / 智谱都能直接用。"""

    def __init__(self, model: str | None = None, dim: int | None = None) -> None:
        self.model = model or settings.ai_embedding_model
        self.dim = dim or settings.ai_embedding_dim

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        out: list[list[float]] = []
        for start in range(0, len(texts), EMBED_BATCH):
            batch = list(texts[start : start + EMBED_BATCH])
            try:
                resp = await _client().embeddings.create(
                    model=self.model,
                    input=batch,
                    dimensions=self.dim,
                    encoding_format="float",
                )
            except Exception as e:
                raise ModelError(f"向量化失败：{_explain(e)}") from e

            # ★ 必须按 index 重排。接口文档不保证返回顺序和入参一致，
            #   一旦错位，向量就会和文本对不上 —— 检索出来的东西
            #   看起来「有结果」但全是错的，而且不报任何错。
            ordered = sorted(resp.data, key=lambda d: d.index)
            out.extend(item.embedding for item in ordered)

        return out


class DashScopeChat:
    def __init__(self, model: str | None = None, thinking: bool | None = None) -> None:
        self.model = model or settings.ai_chat_model
        self.thinking = settings.ai_chat_thinking if thinking is None else thinking

    async def stream(self, messages: Sequence[dict[str, str]]) -> AsyncIterator[str]:
        try:
            stream = await _client().chat.completions.create(
                model=self.model,
                messages=list(messages),
                stream=True,
                # 思考模式开关。百炼用它扩展了 OpenAI 的参数，所以走 extra_body。
                extra_body={"enable_thinking": self.thinking},
            )
        except Exception as e:
            raise ModelError(f"调用对话模型失败：{_explain(e)}") from e

        try:
            async for chunk in stream:
                # 末尾那个带 usage 的块 choices 是空数组，跳过
                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # ★★ 只取 content。开思考模式时 delta 里还多一个 reasoning_content
                #    字段，装的是模型的**内心独白**（实测「1+1 等于几」都能产出
                #    200+ token 的推理过程）。一旦图省事写成
                #        delta.content or getattr(delta, "reasoning_content", "")
                #    模型的思考过程就会直接漏进用户看到的回答里。
                #    现在思考模式默认关着，但这个字段不会因此永远不出现 ——
                #    用户随时可以把 AI_CHAT_THINKING 改成 true。
                piece = delta.content
                if piece:
                    yield piece
        except Exception as e:
            raise ModelError(f"生成回答时中断：{_explain(e)}") from e


# ============================ 假实现（测试用） ============================


class FakeEmbedding:
    """离线向量化：用字符 n-gram 哈希造一个确定性的向量。

    不是随机数 —— **同样的文本永远得到同样的向量，且共享字词越多相似度越高**，
    所以用它跑出来的检索结果是有意义的，能真正验证「切块 → 存储 → 检索 → 排序」
    这条链路，而不只是「没崩」。
    """

    def __init__(self, dim: int = 64) -> None:
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        grams = list(text) + [text[i : i + 2] for i in range(len(text) - 1)]
        for gram in grams:
            # 用 crc32 而不是内置 hash()：后者对 str 加了随机盐，
            # 同一个词在不同进程里结果不同，测试会时灵时不灵。
            bucket = zlib.crc32(gram.encode("utf-8")) % self.dim
            vec[bucket] += 1.0

        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec] if norm else vec

    async def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]


class FakeChat:
    """离线对话：把收到的消息条数和上下文长度报出来，并按固定大小分片。

    `calls` 记录每次收到的完整 messages，测试可以据此断言
    「检索到的分块确实被拼进了 prompt」。
    """

    def __init__(self, reply: str | None = None, piece: int = 6) -> None:
        self.reply = reply
        self.piece = piece
        self.calls: list[list[dict[str, str]]] = []

    async def stream(self, messages: Sequence[dict[str, str]]) -> AsyncIterator[str]:
        self.calls.append([dict(m) for m in messages])
        text = self.reply or (
            f"（离线模拟回答）收到 {len(messages)} 条消息，"
            f"上下文共 {sum(len(m['content']) for m in messages)} 字。"
        )
        for i in range(0, len(text), self.piece):
            yield text[i : i + self.piece]


# ============================ provider 工厂 ============================


class MissingKey(ModelError):
    pass


def _require_key() -> None:
    if not settings.dashscope_api_key:
        raise MissingKey(
            "还没有配置模型 API Key。复制 backend/.env.example 成 backend/.env，"
            "填入 DASHSCOPE_API_KEY 后重启服务即可。"
            "（其余模块不受影响，可以照常使用）"
        )


_override: tuple[EmbeddingProvider | None, ChatProvider | None] = (None, None)


def set_providers(
    embedding: EmbeddingProvider | None = None, chat: ChatProvider | None = None
) -> None:
    """测试专用：换成假 provider。传 None 表示恢复真实实现。"""
    global _override
    _override = (embedding, chat)


def get_embedding_provider() -> EmbeddingProvider:
    if _override[0] is not None:
        return _override[0]
    _require_key()
    return DashScopeEmbedding()


def get_chat_provider() -> ChatProvider:
    if _override[1] is not None:
        return _override[1]
    _require_key()
    return DashScopeChat()
