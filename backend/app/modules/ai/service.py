"""AI 问答模块的业务逻辑。

**这是全项目唯一一处真实的跨模块依赖**，依赖方向是单向的：ai → article。

本模块需要文章正文来做切块，但 articles 表归文章模块所有，所以：

    允许：article_service.get_content(db, id) / list_article_ids(db)
    禁止：from app.modules.article.models import Article

关于「文章改了知识库怎么同步」：按功能清单 F11 的设计，重建索引是**手动点按钮**
触发的，由本模块主动去拉文章，所以**不需要文章模块反过来通知本模块**。
如果做成自动同步，这里立刻就会出现双向依赖 —— 这是当初把它设计成手动触发的原因。
"""

import json
import time
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass

import numpy as np
from fastapi import HTTPException, status as http_status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import settings
from app.core.database import SessionLocal, utcnow
from app.modules.ai import chunking, providers
from app.modules.ai.models import (
    ChatMessage,
    ChatSession,
    KbRebuildState,
    KnowledgeChunk,
    MessageRole,
    RebuildStatus,
)
from app.modules.ai.schemas import Citation, KbStatusOut, RebuildOut
from app.modules.article import service as article_service

# 数据库里只存一行状态，固定主键
_STATE_ID = 1

# 本进程里有没有重建任务在跑。存的是**开始时刻**（time.monotonic），不是布尔值。
#
# ★ 这个进程内的标记是「自愈」机制的关键，用来区分两种
#   「数据库里写着 running」：
#     1. 真的在跑 —— 本进程刚触发的
#     2. 僵尸状态 —— 上个进程触发的，进程重启时任务就没了（BackgroundTasks
#        跑在进程内），但数据库里的状态还留着
#   没有它的话，第 2 种情况会让界面永远显示「正在重建」，
#   而且重新触发会被 409 挡住 —— 功能就此卡死，只能手动改数据库。
#
# ★ 那为什么存时间戳而不是 True/False：清除它的唯一地方是 run_rebuild 的
#   finally，**万一后台任务压根没跑起来**（响应发送失败、客户端在响应返回前
#   断开，Starlette 就不会执行后台任务），这个标记就永远是「在跑」——
#   用户拿到永久性的 409，只能重启服务才能解开。
#   这正是上面那段话在花力气避免的「卡死」，不能在这里自己又制造一个。
#   加上时长判断之后，超时就会被当成死掉的标志放行，自己恢复。
_running_since: float | None = None

# 超过这个时长还没结束，就认为那个任务已经不存在了。
# 取值要**远大于**一次正常重建的耗时：几百篇文章约几分钟，
# 定 30 分钟留足了余量，不会把一次正常的长重建误判成死掉。
_REBUILD_STALE_AFTER = 30 * 60


def _is_rebuilding() -> bool:
    """本进程里当前是否真的有一个重建任务在跑。"""
    if _running_since is None:
        return False
    if time.monotonic() - _running_since > _REBUILD_STALE_AFTER:
        return False
    return True

# 对话时带上的历史消息条数上限（不含本次提问）。
# 带太多会让每轮对话的 token 成本线性上涨，而追问基本只依赖最近一两轮。
_HISTORY_LIMIT = 6


# ====================================================================
# 一、向量缓存
# ====================================================================

# (模型名, 维度, 分块 id 列表, 向量矩阵)
_vec_cache: tuple[str, int, list[int], np.ndarray] | None = None


def invalidate_vector_cache() -> None:
    """重建索引后必须调用。

    忘了调不会报错，只会一直用旧向量回答 —— 那种「改了文章但回答没变」
    的 bug 极难定位。
    """
    global _vec_cache
    _vec_cache = None


def _load_matrix(db: Session) -> tuple[list[int], np.ndarray]:
    """把当前 embedding 模型的全部向量一次读进内存。

    **为什么缓存**：技术栈文档 3.7 节实测，从磁盘读回 16000 个向量要 192ms，
    比检索本身（3.68ms）还慢五十倍。缓存之后每次问答只花检索那部分时间。

    **为什么懒加载而不是启动时加载**：不是每个人都会用 AI 模块，
    没必要为了它让服务一启动就常驻几十 MB。第一次提问时加载一次即可。

    ★ **只加载当前模型 + 当前维度的块**。旧模型生成的向量和新问题不在同一个
      向量空间，参与检索会返回完全无关的内容，而且**一路不报错** ——
      只会让回答变得莫名其妙。宁可当成没有，也不要用错。
      （有多少块被这样排除掉了，kb_status 会报出来。）
    """
    global _vec_cache

    model, dim = settings.ai_embedding_model, settings.ai_embedding_dim
    if _vec_cache is not None and _vec_cache[0] == model and _vec_cache[1] == dim:
        return _vec_cache[2], _vec_cache[3]

    rows = db.execute(
        select(KnowledgeChunk.id, KnowledgeChunk.vector)
        .where(KnowledgeChunk.embedding_model == model)
        .where(KnowledgeChunk.vector_dim == dim)
        .order_by(KnowledgeChunk.id)
    ).all()

    if not rows:
        _vec_cache = (model, dim, [], np.zeros((0, dim), dtype=np.float32))
        return _vec_cache[2], _vec_cache[3]

    # 每行必须是 dim 个 float32。长度对不上的话，b"".join 拼出来的字节流
    # 会错位，reshape 出来的矩阵从某一行开始整体串位 —— 又是一次不报错的错误。
    expected = dim * 4
    broken = [r[0] for r in rows if len(r[1]) != expected]
    if broken:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                f"知识库里的向量数据损坏：分块 {broken[:5]} 的字节数不是 "
                f"{dim} 维该有的 {expected}。点一次「重建索引」可以修复。"
            ),
        )

    ids = [r[0] for r in rows]
    matrix = np.frombuffer(b"".join(r[1] for r in rows), dtype=np.float32).reshape(
        len(rows), dim
    )
    _vec_cache = (model, dim, ids, matrix)
    return ids, matrix


async def _embed_query(text: str) -> np.ndarray:
    vectors = await providers.get_embedding_provider().embed([text])
    if not vectors:
        raise providers.ModelError("向量化返回了空结果")
    return np.asarray(vectors[0], dtype=np.float32)


# ====================================================================
# 二、检索
# ====================================================================


@dataclass(slots=True)
class Hit:
    """一次检索命中的分块。"""

    article_id: int
    title: str
    chunk_index: int
    score: float
    text: str

    def to_citation(self) -> Citation:
        return Citation(
            article_id=self.article_id,
            title=self.title,
            score=round(self.score, 4),
            chunk_index=self.chunk_index,
        )


def _title_from_chunk(chunk_text: str) -> str:
    """兜底取标题。

    chunk_text 的第一行是我们自己写进去的文章标题（见 chunking.chunk_article）。
    只有文章在这期间被删掉、`get_content` 拿不到标题时才走这里。
    """
    return chunk_text.split("\n", 1)[0].strip() or "（文章已删除）"


async def retrieve(db: Session, question: str) -> list[Hit]:
    """在知识库里检索和问题最相关的分块。

    **返回空列表就代表「知识库里没有相关内容」** —— 这正是 F13 的判定条件，
    不是一个单独的接口。做成两个接口的话，前端得先猜「我这个问题知识库里
    有没有」，猜错就白跑一次往返和一次 embedding 调用。
    """
    ids, matrix = _load_matrix(db)
    if not ids:
        return []

    query = await _embed_query(question)
    if query.shape[0] != matrix.shape[1]:
        raise providers.ModelError(
            f"问题向量是 {query.shape[0]} 维，知识库里是 {matrix.shape[1]} 维。"
            "检查 .env 里的 AI_EMBEDDING_MODEL 和 AI_EMBEDDING_DIM 是否配套，"
            "然后点一次「重建索引」。"
        )

    # 余弦相似度 = 两个向量各自归一化之后的点积。
    # 不能直接点积就完事：存进去的向量不一定归一化过。
    q = query / (np.linalg.norm(query) or 1.0)
    norms = np.linalg.norm(matrix, axis=1)
    norms[norms == 0] = 1.0
    sims = (matrix / norms[:, None]) @ q

    k = min(settings.ai_retrieval_top_k, len(ids))
    if k < len(ids):
        # argpartition 是 O(n) 的，只需要把前 k 个挑出来；
        # 全排序是 O(n log n)，对几千个块来说白费。
        top = np.argpartition(-sims, k - 1)[:k]
    else:
        top = np.arange(len(ids))
    top = top[np.argsort(-sims[top])]

    # ★ 阈值过滤 —— 这一行就是 F12 和 F13 的分界线。
    #   过不了阈值就当作知识库里没有，交给通用模型回答并明确标注。
    threshold = settings.ai_retrieval_min_score
    picked = [(ids[i], float(sims[i])) for i in top if sims[i] >= threshold]
    if not picked:
        return []

    rows = {
        c.id: c
        for c in db.scalars(
            select(KnowledgeChunk).where(
                KnowledgeChunk.id.in_([p[0] for p in picked])
            )
        )
    }

    hits: list[Hit] = []
    for chunk_id, score in picked:
        chunk = rows.get(chunk_id)
        # 缓存和库不一致（比如刚重建过、id 已经变了），跳过就好，不影响别的结果
        if chunk is None:
            continue

        # 走文章模块暴露的接口拿标题，不碰它的表。
        # 这里多查几次是刻意的：标题是引用来源要显示的东西，
        # 必须和文章模块当前的状态一致。
        info = article_service.get_content(db, chunk.article_id)
        hits.append(
            Hit(
                article_id=chunk.article_id,
                title=info["title"] if info else _title_from_chunk(chunk.chunk_text),
                chunk_index=chunk.chunk_index,
                score=score,
                text=chunk.chunk_text,
            )
        )
    return hits


# ====================================================================
# 三、知识库状态与重建
# ====================================================================


def _get_state(db: Session) -> KbRebuildState | None:
    return db.get(KbRebuildState, _STATE_ID)


def kb_status(db: Session) -> KbStatusOut:
    """AI1 · 知识库状态。"""
    chunk_count = db.scalar(select(func.count()).select_from(KnowledgeChunk)) or 0
    stale = (
        db.scalar(
            select(func.count())
            .select_from(KnowledgeChunk)
            .where(
                (KnowledgeChunk.embedding_model != settings.ai_embedding_model)
                | (KnowledgeChunk.vector_dim != settings.ai_embedding_dim)
            )
        )
        or 0
    )

    state = _get_state(db)
    return KbStatusOut(
        article_count=len(article_service.list_article_ids(db)),
        chunk_count=chunk_count,
        embedding_model=settings.ai_embedding_model,
        embedding_dim=settings.ai_embedding_dim,
        stale_chunk_count=stale,
        last_rebuilt_at=state.last_success_at if state else None,
        last_error=state.last_error if state else None,
    )


def _heal_interrupted(db: Session, state: KbRebuildState | None) -> KbRebuildState | None:
    """把僵尸的 running 状态修成 interrupted，返回修好之后的状态。

    判据：数据库说在跑，但**本进程里并没有任务**。任务跑在进程内，
    进程重启它就没了 —— 所以这种状态一定是上一个进程留下的。

    做成「读取时顺手修」而不是「服务启动时清理」，有两个好处：
      1. 不需要给 main.py 加启动钩子（那个文件明确写着新增模块不许改）
      2. 自愈发生在用户去看的那一刻，不管服务重启过几次
    """
    if state is None or state.status != RebuildStatus.RUNNING or _is_rebuilding():
        return state

    state.status = RebuildStatus.INTERRUPTED
    state.finished_at = utcnow()
    state.last_error = "服务重启，重建任务被中断。重新点一次「重建索引」即可。"
    db.commit()
    return state


def rebuild_progress(db: Session) -> RebuildOut:
    """AI3 · 重建进度。从来没跑过时返回一个全零的 idle。"""
    state = _heal_interrupted(db, _get_state(db))
    if state is None:
        return RebuildOut(status=RebuildStatus.IDLE, total=0, done=0, failed=0)
    return RebuildOut(
        status=state.status,
        total=state.total,
        done=state.done,
        failed=state.failed,
        last_error=state.last_error,
        started_at=state.started_at,
        finished_at=state.finished_at,
    )


def begin_rebuild(db: Session) -> list[int]:
    """AI2 · 占位并返回本次要处理的所有文章 ID。

    **只做「把状态改成 running」这一件事，真正的重建由调用方丢进后台任务。**
    全量重建是分钟级的，HTTP 请求等不了那么久。

    返回文章 ID 列表是为了让后台任务拿到一份**权威白名单** ——
    重建结束时要靠它清理孤儿块（文章已被删除、分块还留着）。
    """
    global _running_since

    state = _get_state(db)
    if state is not None and state.status == RebuildStatus.RUNNING:
        # 真的在跑才拒绝。僵尸状态（上个进程留下的、或者任务没跑起来的）不挡，
        # 直接覆盖重来 —— 否则用户会被一个根本不存在的前置任务永久卡住，
        # 只能去改数据库或者重启服务。
        if _is_rebuilding():
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="已经有一个重建任务在进行中，等它跑完再试。",
            )
        state.last_error = "上一次重建意外中断了，已重新开始。"

    if state is None:
        state = KbRebuildState(id=_STATE_ID)
        db.add(state)

    state.status = RebuildStatus.RUNNING
    state.total = 0
    state.done = 0
    state.failed = 0
    state.started_at = utcnow()
    state.finished_at = None
    db.commit()

    # ★ 在**响应返回之前**就打上标记。不能等 run_rebuild 自己开头再打 ——
    #   前端触发重建后会立刻开始轮询进度，而 BackgroundTasks 要等响应发完才跑，
    #   中间那个空窗期里标记还没设，轮询会把刚启动的任务误判成僵尸状态改掉。
    _running_since = time.monotonic()

    return article_service.list_article_ids(db)


async def run_rebuild(article_ids: Sequence[int]) -> None:
    """后台任务：全量重建知识库。

    ★ **自己开一个数据库会话，不能用请求那个。**
      请求的会话在响应发出时就被依赖注入关掉了，而 BackgroundTasks
      恰恰是在响应**之后**才跑 —— 复用会拿到一个已关闭的会话。

    为什么是全量而不是增量：个人文章量级（几百篇）全量重跑一次的成本可以接受，
    而增量同步要额外维护「哪篇脏了」的状态，是复杂度的净增加。
    """
    global _running_since

    db = SessionLocal()
    try:
        state = _get_state(db)
        if state is None or state.status != RebuildStatus.RUNNING:
            # 状态在排队期间被别处改掉了，那就别跑了
            return

        embedder = providers.get_embedding_provider()
        state.total = len(article_ids)
        db.commit()

        errors: list[str] = []

        for article_id in article_ids:
            try:
                await _reindex_one(db, article_id, embedder)
            except Exception as e:
                # ★ 单篇失败**不中断整个任务**。一个人写的文章里，
                #   偶尔有一篇内容异常不该让前面几百篇白跑。
                #   注意这里回滚的是这一篇的事务，旧的块因此得以保留 ——
                #   宁可留着旧内容，也不要因为一次网络抖动把文章从知识库里抹掉。
                db.rollback()
                state = _get_state(db)
                if state is None:
                    return
                state.failed += 1
                errors.append(f"文章 {article_id}：{e}")
            else:
                db.commit()

            state.done += 1
            # 每篇一提交，前端的进度条才能实时动 —— 攒到最后一起提交的话，
            # 用户会看到进度条从 0% 直接跳到 100%。
            db.commit()

        # 清理孤儿块：按文章模块给的**白名单**删，而不是按「本次成功处理过的」。
        # 用后者的话，一篇因为网络抖动失败的文章，它的旧块会被当成孤儿删掉 ——
        # 一次抖动就等于把这篇从知识库里抹了。不可接受。
        _delete_orphans(db, article_ids)

        state = _get_state(db)
        if state is None:
            return
        state.finished_at = utcnow()

        # ★ 这里必须是**赋值**而不是「有错误才写」。
        #   只在有错误时写的话，上一次失败留下的信息会永远挂着 ——
        #   用户明明跑了一次完全成功的重建，状态接口里却报着一条错误。
        #   （begin_rebuild 也会往这里写「上次被中断了」之类的提示，
        #   那些同样要在这里被本次的真实结果覆盖掉。）
        state.last_error = errors[-1] if errors else None

        # 全军覆没才算失败；有成功有失败仍然算完成，失败情况由 failed 计数体现
        if article_ids and state.failed >= state.total:
            state.status = RebuildStatus.FAILED
        else:
            state.status = RebuildStatus.DONE
            state.last_success_at = utcnow()
        db.commit()
    finally:
        # 标志必须清掉，否则下一次重建会被 409 挡住（而且这只是第一道防线，
        # 真正兜底的是 _is_rebuilding 里的超时判断）
        _running_since = None
        db.close()
        # 无论成败都要让缓存失效：成功时是必须换新向量，
        # 失败时可能已经写进去了一部分，留着旧缓存反而更不一致。
        invalidate_vector_cache()


async def _reindex_one(
    db: Session, article_id: int, embedder: providers.EmbeddingProvider
) -> None:
    """重建一篇文章的分块。**不提交事务**，提交由调用方按篇控制。"""
    content = article_service.get_content(db, article_id)

    # 拿不到正文有两种情况：文章被删了、或进了回收站。
    # 都不算失败 —— 把它们的分块清掉就对了。
    if content is None:
        db.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.article_id == article_id)
        )
        return

    texts = chunking.chunk_article(
        title=content["title"],
        content_text=content["content_text"],
        size=settings.ai_chunk_size,
        overlap=settings.ai_chunk_overlap,
    )

    # 只有标题、没有正文的文章切出来的块是空的，同样清掉
    if not texts:
        db.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.article_id == article_id)
        )
        return

    vectors = await embedder.embed(texts)
    if len(vectors) != len(texts):
        raise providers.ModelError(
            f"向量化返回了 {len(vectors)} 条，但切出了 {len(texts)} 块"
        )

    model = settings.ai_embedding_model
    rows: list[KnowledgeChunk] = []
    for index, (text, vector) in enumerate(zip(texts, vectors)):
        arr = np.asarray(vector, dtype=np.float32)
        rows.append(
            KnowledgeChunk(
                article_id=article_id,
                chunk_index=index,
                chunk_text=text,
                vector=arr.tobytes(),
                vector_dim=arr.shape[0],
                embedding_model=model,
            )
        )

    # ★ 先删旧块再写新块，且在**同一个事务**里。
    #   反过来（先写后删）会撞上 uq_knowledge_chunk_article_index 唯一约束；
    #   分成两个事务则会在中途失败时留下半新半旧的一篇文章。
    db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.article_id == article_id))
    db.add_all(rows)


def _delete_orphans(db: Session, keep: Sequence[int]) -> None:
    """删掉不属于任何现存文章的分块。

    不清理的话，一篇被删掉的文章留下的分块仍然会被检索到，
    模型会引用一篇已经不存在的文章来回答 —— 用户看到的引用来源点进去是 404。
    """
    stmt = delete(KnowledgeChunk)
    if keep:
        stmt = stmt.where(KnowledgeChunk.article_id.notin_(list(keep)))
    db.execute(stmt)


# ====================================================================
# 四、问答
# ====================================================================

_SYSTEM_WITH_KB = """你是我的私人知识库助手。下面是我从**自己写的文章**里检索出来的内容。

回答规则：

1. 优先用下面的内容回答，用到哪篇就用《文章标题》标出出处。

2. 下面的内容不够时，可以用你自己的知识补充 —— 但**必须把补充的部分单独标出来**，
   让我一眼能分清哪些话是我文章里说的、哪些是你加进来的：

   - 来自我文章的内容：正常写，带上《文章标题》
   - 你自己补充的内容：**另起一段**，以「**以下是我的补充，你的文章里没有**」开头

   不要把两者写在同一个段落里，也不要只在句子里夹一个词就算区分了。

3. 如果下面的内容已经够回答，就只讲文章里的，**不要画蛇添足地补充**。

4. 用中文，简洁直接，不要寒暄。

检索到的内容：
{context}"""

_SYSTEM_NO_KB = """我的知识库里没有找到和这个问题相关的内容。

所以这一次请用你自己的通用知识回答，不要假装是我文章里的内容。
用中文，简洁直接。"""


def _build_context(hits: Sequence[Hit]) -> str:
    blocks = []
    for i, hit in enumerate(hits, 1):
        blocks.append(
            f"--- 片段 {i} · 来源《{hit.title}》· 相关度 {hit.score:.2f} ---\n{hit.text}"
        )
    return "\n\n".join(blocks)


def _build_messages(
    question: str, hits: Sequence[Hit], history: Sequence[ChatMessage]
) -> list[dict[str, str]]:
    system = _SYSTEM_WITH_KB.format(context=_build_context(hits)) if hits else _SYSTEM_NO_KB

    messages: list[dict[str, str]] = [{"role": "system", "content": system}]
    # 带上最近几轮，追问（「那第二点呢」）才有上下文。
    # 条数有上限，否则每轮对话的 token 成本会线性上涨。
    for msg in history:
        messages.append({"role": msg.role, "content": msg.content})
    messages.append({"role": "user", "content": question})
    return messages


def _save_message(
    db: Session,
    session: ChatSession,
    role: str,
    content: str,
    used_knowledge: bool = True,
    citations: Sequence[Citation] = (),
) -> ChatMessage:
    message = ChatMessage(
        session_id=session.id,
        role=role,
        content=content,
        used_knowledge=used_knowledge,
        # 标题一起存进来，这样**文章以后被删掉，历史回答的引用来源仍然显示得出来**
        citations=json.dumps(
            [c.model_dump() for c in citations], ensure_ascii=False
        )
        if citations
        else None,
    )
    db.add(message)

    # 顺手把会话的 updated_at 顶上去，会话列表才能按「最近聊过的」排序。
    # ChatSession 的 onupdate 只在这一行本身被改动时才触发，
    # 加一条消息并不会碰到它。
    session.updated_at = utcnow()

    db.commit()
    db.refresh(message)
    return message


async def stream_answer(
    session_id: int, question: str
) -> AsyncIterator[tuple[str, dict]]:
    """AI8 · 提问。产出 `(事件名, 数据)` 对，由 router 转成 SSE 文本。

    **自己开会话**，理由同 run_rebuild：流式响应期间请求的依赖注入会话
    可能已经被关掉了。会话是否存在由 router 用请求的会话提前校验，
    这样「会话不存在」仍然是一个正常的 404，而不是流里的一条 error 事件。
    """
    db = SessionLocal()
    try:
        session = db.get(ChatSession, session_id)
        if session is None:
            yield "error", {"detail": "会话不存在"}
            return

        history = list(
            db.scalars(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.id.desc())
                .limit(_HISTORY_LIMIT)
            )
        )[::-1]  # 取最近 N 条，再翻回正序

        _save_message(db, session, MessageRole.USER, question)

        # ---- 检索：F12 / F13 在这里分岔 ----
        try:
            hits = await retrieve(db, question)
        except providers.ModelError as e:
            yield "error", {"detail": str(e)}
            return

        citations = [h.to_citation() for h in hits]
        used_knowledge = bool(hits)

        # ★ meta 放在流的最开头，而不是等回答生成完再发。
        #   检索在生成之前就做完了，所以「找到了这几篇」可以**立刻**显示 ——
        #   用户先知道依据是什么，再读回答，不用干等十几秒才知道有没有引用上。
        yield "meta", {
            "used_knowledge": used_knowledge,
            "citations": [c.model_dump() for c in citations],
        }

        messages = _build_messages(question, hits, history)
        chat = providers.get_chat_provider()

        parts: list[str] = []
        saved: ChatMessage | None = None
        try:
            async for piece in chat.stream(messages):
                parts.append(piece)
                yield "delta", {"text": piece}

            saved = _save_message(
                db,
                session,
                MessageRole.ASSISTANT,
                "".join(parts),
                used_knowledge=used_knowledge,
                citations=citations,
            )
        except providers.ModelError as e:
            yield "error", {"detail": str(e)}
        finally:
            # ★ 不管是正常结束、模型报错，还是**用户中途关掉了页面**
            #   （那会让这个生成器收到 GeneratorExit），已经生成的部分都要落库。
            #   宁可存半截回答，也不要让用户回来看到一个空白的回复框。
            if saved is None and parts:
                _save_message(
                    db,
                    session,
                    MessageRole.ASSISTANT,
                    "".join(parts),
                    used_knowledge=used_knowledge,
                    citations=citations,
                )

        if saved is not None:
            yield "done", {"message_id": saved.id}
    finally:
        db.close()


# ====================================================================
# 五、会话管理
# ====================================================================


def list_sessions(db: Session) -> list[ChatSession]:
    """AI4 · 会话列表，最近聊过的在前。

    **不分页**：单人自用，会话数量有限；真多到需要翻页了再加。
    """
    return list(db.scalars(select(ChatSession).order_by(ChatSession.updated_at.desc())))


def create_session(db: Session, title: str | None) -> ChatSession:
    """AI5 · 新建会话。

    **不自动用模型生成标题**：那要额外调一次模型，占一次额度和一次延迟，
    而收益只是列表里好看一点。前端拿第一句提问的前 20 个字当标题就够用了。
    """
    session = ChatSession(title=(title or "").strip() or "新对话")
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def get_session(db: Session, session_id: int) -> ChatSession:
    """AI6 · 会话详情（含全部消息，按时间正序）。"""
    session = db.scalar(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .options(selectinload(ChatSession.messages))
    )
    if session is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="会话不存在"
        )
    return session


def ensure_session_exists(db: Session, session_id: int) -> None:
    if db.get(ChatSession, session_id) is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="会话不存在"
        )


def delete_session(db: Session, session_id: int) -> None:
    """AI7 · 删除会话。

    消息靠 `ChatSession.messages` 上的 `cascade="all, delete-orphan"` 一起删。
    **不能指望数据库的 ON DELETE CASCADE** —— 本项目没有启用外键校验
    （见数据库设计第七章第 1 条），数据库不会替我们做这件事。
    """
    session = db.get(ChatSession, session_id)
    if session is None:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND, detail="会话不存在"
        )
    db.delete(session)
    db.commit()
