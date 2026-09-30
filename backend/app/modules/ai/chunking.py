"""文章切块。

**纯函数，不碰数据库也不碰模型**，所以可以脱离一切外部依赖单独测试 ——
这是刻意的：切块质量直接决定检索质量，而它又是整个模块里最容易悄悄变坏的一环。

为什么要重叠（overlap）：答案往往正好落在两块的边界上，不重叠的话，前一块有
问题描述、后一块有答案，检索出任何一块都不完整。重叠让边界上的内容同时出现在
相邻两块里。
"""

import re

# 段之间：一个空行。中文文章里 \n\n 和 \n 都有人用，所以两个都认。
_PARA = re.compile(r"\n\s*\n|\n")

# 句子边界：中英文句末标点。用「零宽断言」保留标点本身 —— 直接 split 会把标点吃掉。
_SENT = re.compile(r"(?<=[。！？!?；;：:])")

# 尾块短于这个长度就并进上一块。
# 一个 20 字的块在向量检索里几乎没有信息量，却会占一个 top-k 名额。
MIN_TAIL = 50


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in _PARA.split(text) if p.strip()]


def _split_sentences(para: str) -> list[str]:
    return [s.strip() for s in _SENT.split(para) if s.strip()]


def _hard_split(text: str, size: int) -> list[str]:
    """兜底：没有任何标点的超长文本（比如一整段英文代码）只能按字数硬切。"""
    return [text[i : i + size] for i in range(0, len(text), size)]


def _to_units(text: str, size: int) -> list[str]:
    """把正文拆成「单元」—— 每个单元都 <= size，且尽量落在自然边界上。

    优先级：段落 > 句子 > 硬切。逐级降级，保证不会返回超长单元。
    """
    units: list[str] = []
    for para in _split_paragraphs(text):
        if len(para) <= size:
            units.append(para)
            continue

        for sent in _split_sentences(para):
            if len(sent) <= size:
                units.append(sent)
            else:
                units.extend(_hard_split(sent, size))
    return units


def split_text(text: str, size: int = 500, overlap: int = 100) -> list[str]:
    """把一段正文切成若干块。返回的每块 <= size（尾块例外，见下）。

    size 和 overlap 都按**字符数**算 —— 中文一个字一个字符。
    """
    text = text.strip()
    if not text:
        return []
    # 短文章不切，整篇就是一块。避免为几十个字的文章造出一堆碎片。
    if len(text) <= size:
        return [text]

    units = _to_units(text, size)

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for unit in units:
        if current and current_len + len(unit) > size:
            chunks.append("\n".join(current))

            # 回带重叠：从上一块**尾部**取单元放到新块开头。
            # 按单元取而不是按字符取 —— 按字符取会把一句话拦腰截断，
            # 那半句话既读不通，向量也是噪声。
            carry: list[str] = []
            carried = 0
            for prev in reversed(current):
                if carried >= overlap:
                    break
                # 带了就装不下当前单元，那就不带 —— 宁可这块没有重叠，
                # 也不要造出一个超过 size 的块。
                if carried + len(prev) + len(unit) > size:
                    break
                carry.insert(0, prev)
                carried += len(prev)
            current = carry
            current_len = carried

        current.append(unit)
        current_len += len(unit)

    if current:
        chunks.append("\n".join(current))

    # 尾块太短就并进上一块。这会产出一个略超 size 的块，但比留一块
    # 没信息量的碎片划算。
    if len(chunks) >= 2 and len(chunks[-1]) < MIN_TAIL:
        chunks[-2] = chunks[-2] + "\n" + chunks[-1]
        chunks.pop()

    return chunks


def chunk_article(
    title: str, content_text: str, size: int = 500, overlap: int = 100
) -> list[str]:
    """把一篇文章切成块，每块带上文章标题。

    **为什么要带标题**：标题是最强的检索信号。问「租房合同要注意什么」时，
    标题里就有这几个字的文章理应排在前面；而正文里可能一次都没提「租房合同」
    这四个字（通篇在讲押金、违约、退租）。标题跟着每一块走，
    这一块的向量里就有标题的语义。

    代价：文章改标题后需要重建索引。而重建本来就是手动触发的，
    这个代价可以接受。

    ★ 传进来的必须是**纯文本**（article.content_text），绝不能是 HTML ——
    HTML 标签会污染语义匹配，这是数据库设计里把两个正文字段分开存的原因。
    """
    title = (title or "").strip()
    blocks = split_text(content_text, size=size, overlap=overlap)

    if not title:
        return blocks
    # 标题独立成行放在块首，后面空一行再跟正文 —— 这样模型的 prompt 里
    # 也能一眼看出块是从哪篇文章来的。
    return [f"{title}\n\n{b}" for b in blocks]
