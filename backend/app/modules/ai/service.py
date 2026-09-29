"""AI 问答模块的业务逻辑。

**这是全项目唯一一处真实的跨模块依赖**，依赖方向是单向的：ai → article。

本模块需要文章正文来做切块，但 articles 表归文章模块所有，所以：

    允许：from app.modules.article.service import get_content
    禁止：from app.modules.article.models import Article

关于「文章改了知识库怎么同步」：按功能清单 F11 的设计，重建索引是**手动点按钮**
触发的，由本模块主动去拉文章，所以**不需要文章模块反过来通知本模块**。
如果做成自动同步，这里立刻就会出现双向依赖 —— 这是当初把它设计成手动触发的原因。

模型调用（embedding 与对话）统一走 openai SDK，换供应商只改 base_url，
具体封装在「接口设计」阶段之后补上。
"""
