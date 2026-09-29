# Freedom Design 个人工作台 架构设计文档

> 文档版本：v1.0
> 生成日期：2026-09-29
> 上游依赖：docs/feature_list/feature_list.md、docs/tech_stack/tech_stack.md
> 关联文档：docs/feature_list/feature_list.md 第六节（模块化约束）、docs/tech_stack/tech_stack.md

## 一、架构要解决的问题

这份架构只有一个核心目标：**让"新增一个功能模块"的成本固定下来，而且不随模块数量增长。**

功能清单第六节已经把它拆成了硬约束，这里逐条给出落地方式：

| 功能清单里的约束 | 本架构怎么落地 |
|------------------|----------------|
| 模块化竖切，模块自带路由、逻辑、数据表 | 第三章：每个模块是一个自包含的目录 |
| 模块清单驱动路由与导航 | 第四章：前后端各一份注册表 |
| 新增模块只新增文件，不改已有模块 | 第七章：完整清单 + 末尾的验收方法 |
| 模块之间只走接口，不碰对方的表 | 第五章、第六章 |
| 数据库选型要支撑所有未来的模块 | 技术栈选型已定 SQLite，第三章说明表怎么分 |

**这份文档的唯一验收标准**：第七章的清单走完一遍，`git diff` 里不该出现任何已有模块的文件。

## 二、整体结构

整个系统分三层，依赖方向是**单向的**：

```
    modules（业务层）  ── 依赖 ──▶  core（骨架层）
    文章 / 计划 / AI …            配置、数据库、认证、注册表
```

- **core（骨架层）**：所有模块共用的基础设施。它**不认识任何具体业务**——core 里不该出现 "article" 这个词。
- **modules（业务层）**：一个业务模块一个目录，自包含。模块之间只允许单向依赖对方暴露的服务函数（见第六章）。
- **docs / .claude**：文档与 skill，不参与运行时。

反向依赖是禁止的：core 不许 import modules，模块 A 不许和模块 B 互相 import。

### 项目根目录

```
freedom_design/
├── .gitignore
├── README.md
├── .claude/                    # Claude Code skill
├── docs/                       # 各阶段产出文档
├── backend/
└── frontend/
```

## 三、目录结构

### 3.1 后端

```
backend/
├── .venv/                      # 虚拟环境          （git 忽略）
├── data/                       # SQLite 数据库文件 （git 忽略）
├── uploads/                    # 文章插图          （git 忽略）
├── alembic/                    # 数据库迁移脚本
├── alembic.ini
├── requirements.txt
├── .env                        # 真实密钥          （git 忽略）
├── .env.example
└── app/
    ├── main.py                 # 入口：建 FastAPI → 挂载注册表 → 托管前端静态文件
    ├── core/                   # 骨架层，不含任何业务
    │   ├── config.py           # 读 .env，暴露配置对象
    │   ├── database.py         # SQLAlchemy engine / Session / Base / 时间戳基类
    │   ├── models.py           # 全局表（目前只有 user）
    │   ├── schemas.py          # 骨架层共用的请求 / 响应模型
    │   ├── security.py         # 密码哈希、JWT 签发与校验
    │   ├── deps.py             # 通用依赖，如 get_current_user
    │   ├── router.py           # 骨架层接口：健康检查 + 登录认证 ★ 见下方说明
    │   ├── module.py           # 模块契约（ModuleInfo）
    │   └── registry.py         # 模块注册表
    └── modules/                # 业务层
        ├── article/            # 文章、分类、标签
        ├── plan/               # 待办与计划
        └── ai/                 # 知识库与问答
```

**认证为什么整体属于 core，而不是一个模块**（实现 F1 时定的，v1.0 原文把 auth 列在 modules 下，这点改了）：

一开始确实建了 `modules/auth/`，写登录功能时发现它站不住，理由有三条：

1. **依赖方向**。每个业务模块的接口都要靠 `get_current_user` 鉴权。如果它住在 auth 模块里，那 article、plan、ai 就全都得 import auth，多出一条本不该存在的依赖线——而 auth 自己不依赖任何人，这种单向依赖看着还行，但它让"模块之间互不依赖"这条规则出现了例外
2. **前端更硬的原因**：路由守卫住在 `core/router.ts`，它必须能读到登录态。如果登录态属于某个模块，core 就要反向依赖模块，直接违反第五章的依赖方向铁律
3. **它本来就不是业务**。core 的规则是「不许出现业务名词」，而认证不是业务名词——它和 `security.py`、`deps.py` 是同一类东西

所以认证在两边的归属是：

| | 放哪 | 内容 |
|---|---|---|
| 后端 | `core/router.py` | `/api/health`、`/api/auth/login`、`/logout`、`/me` |
| 后端 | `core/security.py`、`core/deps.py` | 密码哈希、JWT 签发校验、`get_current_user` |
| 前端 | `core/stores/auth.ts`、`core/views/LoginView.vue` | 登录态、登录页 |
| 前端 | `core/router.ts` | 登录页路由 + 全局守卫 |

这些接口由 `main.py` 直接挂载在 `/api` 下，**不经过模块注册表**——因为它们本来就不是模块。

顺带一个判断标准：**登录页必须在 `AppLayout` 之外**（没登录的人不该看见侧边导航），这也从结构上说明它不是普通业务页面。

**core/module.py 为什么单独一个文件**（搭建骨架时新增，原文档漏写了）：它定义 `ModuleInfo` 这个模块契约。如果把它写在 `registry.py` 里会形成循环导入——`registry.py` 要 import 各模块的 `module.py`，而各模块的 `module.py` 又要 import `ModuleInfo`。拆出来之后依赖是单向的：

```
modules/*/module.py  →  core/module.py
core/registry.py     →  modules/*/module.py
```

### 3.2 前端

```
frontend/
├── node_modules/               #                        （git 忽略）
├── dist/                       # 构建产物                （git 忽略）
├── package.json
├── vite.config.ts              # 开发时把 /api 代理到后端 8000 端口
├── .env.development
├── .env.production
└── src/
    ├── main.ts
    ├── App.vue
    ├── core/                   # 骨架层
    │   ├── api.ts              # axios 实例 + 拦截器（自动带 token、401 跳登录）
    │   ├── router.ts           # 路由：从注册表收集各模块的路由 + 登录守卫
    │   ├── module.ts           # 模块契约（ModuleDef 类型）
    │   ├── registry.ts         # 模块注册表
    │   ├── stores/
    │   │   └── auth.ts         # 登录状态 ★ 见下方说明
    │   ├── views/
    │   │   ├── HomeView.vue    # 首页：模块卡片 + 后端连通性检查
    │   │   ├── LoginView.vue   # 登录页（故意在 AppLayout 之外）
    │   │   └── NotFoundView.vue
    │   └── layout/
    │       ├── AppLayout.vue   # 外壳：侧边栏 + 内容区
    │       └── SideNav.vue     # 导航，由注册表生成，不是写死的链接
    └── modules/
        ├── article/
        ├── plan/
        └── ai/
```

## 四、模块的内部结构

### 4.1 后端模块

每个模块目录固定这 6 个文件，职责不混：

| 文件 | 职责 | 约束 |
|------|------|------|
| `module.py` | 模块自描述：模块名、路由前缀 | 只描述，不含逻辑 |
| `models.py` | 本模块的 SQLAlchemy 表 | **只放自己的表**，绝不在别人的模型上加字段 |
| `schemas.py` | Pydantic 请求 / 响应模型 | 与 models 分开，不直接暴露数据库结构 |
| `service.py` | 业务逻辑 | **这个文件里公开的函数就是本模块对外的接口** |
| `router.py` | APIRouter，定义 HTTP 接口 | 只做参数校验和调用 service，不写业务逻辑 |
| `__init__.py` | 空 |

以文章模块为例：

```
app/modules/article/
├── __init__.py
├── module.py
├── models.py       # Article / Category / Tag / ArticleTag
├── schemas.py
├── service.py
└── router.py
```

**关键约定**：`service.py` 里公开的函数（不以 `_` 开头）就是本模块的对外契约。别的模块要数据，只能调这些函数，不许碰 `models.py`。

### 4.2 前端模块

| 文件 / 目录 | 职责 |
|-------------|------|
| `module.ts` | 模块自描述：导航名称、图标、是否默认启用 |
| `routes.ts` | 本模块的路由定义，路径以模块名开头 |
| `api.ts` | 调用本模块后端接口，统一用 core 的 axios 实例 |
| `stores/` | 本模块的 Pinia store（如需要） |
| `views/` | 页面级组件，与 routes 一一对应 |
| `components/` | 本模块专属的组件 |

## 五、模块注册机制

### 5.1 两份注册表

前后端各一份模块清单，都是**显式列表**，不是自动扫描目录。

**为什么不用自动发现**：自动扫描确实能少改一处文件，但它带来的"魔法"对单人项目是负收益——出问题时你没法从代码里一眼看出系统里到底有哪些模块。显式列表多写一行，换来的是随时可读的全貌。

**为什么两份不合并**：后端管路由挂载，前端管导航渲染，两边的关注点不同（比如某个模块可能有接口但没有页面）。强行合并会引入不必要的耦合。代价是新增模块要改两处——这个代价可以接受。

### 5.2 路由挂载

后端 `main.py` 启动时遍历后端注册表，把每个模块的 `router` 按它 `module.py` 里声明的前缀挂上去。

**接口路径约定**：`/api/{模块名}/{资源}`

| 模块 | 前缀 | 示例 |
|------|------|------|
| auth | `/api/auth` | `POST /api/auth/login` |
| article | `/api/article` | `GET /api/article/categories` |
| plan | `/api/plan` | `GET /api/plan/todos` |
| ai | `/api/ai` | `POST /api/ai/chat` |

前端 `core/router.ts` 遍历前端注册表，把各模块的 `routes` 合并进路由表，**并对模块级路由做懒加载**（`() => import(...)`），这样模块多了也不会拖慢首屏。

### 5.3 导航生成

`SideNav.vue` 从注册表读取每个模块的导航信息渲染菜单，**不写死任何链接**。新增模块登记进注册表，导航里自动就出现了。

F18（模块启用与停用）在这一层实现：注册表每条记录带一个启用状态，关掉的模块不出现在导航中，但数据和路由都保留。这个状态**存在浏览器 localStorage 里就够**——它只是显示偏好，没必要为它建数据库表、加接口。代价是换设备不同步，对单用户工具可以接受。

## 六、模块边界的三条铁律

这三条是整套架构能不能撑住"随时加功能"的关键。违反了，三个月后你会发现自己又在动老代码。

### 铁律一：只碰自己的表

模块 A 的 `models.py` 里不许出现模块 B 的表，也不许写 SQL 去 join 模块 B 的表。

**为什么**：一旦 A 直接读 B 的表，B 改了字段结构，A 就会在你完全没想到的时候崩掉。表结构是模块的私事。

### 铁律二：要别人的数据，调别人的 service

模块 A 需要模块 B 的数据时，只有一条路：import 模块 B 的 `service.py` 里公开的函数。

**依赖只允许单向**。如果出现 A 依赖 B、B 又依赖 A，说明这两个模块的边界画错了，要么合并，要么把共用的部分提到 core。**循环依赖是必须立刻处理的信号，不是可以绕过去的麻烦。**

### 铁律三：core 里不许出现业务名词

`core/` 下的任何文件里出现 `article`、`todo`、`chat` 这类词，就说明有业务逻辑漏进骨架层了。core 只应该知道"有模块"这件事，不该知道有哪些模块。

## 七、跨模块调用：AI 模块怎么读文章

这是本项目里唯一一处真实的跨模块需求——知识库要拿文章正文切块，但文章的表归文章模块所有。

**做法**：

1. AI 模块的 `knowledge_chunk` 表里存 `article_id`，但**不建数据库层面的外键约束**（软引用）。理由：外键会让两张表在数据库层面绑死，将来模块拆分或独立部署时会成为障碍。
2. AI 模块需要正文时，调用文章模块 `service.py` 暴露的 `get_content(article_id)`。依赖方向是**单向的：ai → article**。
3. **同步问题不需要反向依赖**。文章改了要重建索引这件事，按功能清单 F11 的设计是**手动点「重建索引」**触发的，是 AI 模块主动去拉文章，不需要文章模块反过来通知 AI 模块。

**如果以后依赖变复杂了**：当出现三个以上模块互相依赖时，再考虑在 core 里加一个简单的事件机制。**现在不要做**——两个模块的单向依赖，直接 import 是最清楚的写法。

## 八、新增一个模块的完整清单

以新增一个「记账」模块为例。照着走完，最后一步的验收会告诉你边界有没有破。

### 8.1 后端

- [ ] 新建目录 `app/modules/ledger/`
- [ ] 写 `models.py` —— 只放本模块的表，继承 core 的 `Base`
- [ ] 写 `schemas.py` —— 请求 / 响应模型
- [ ] 写 `service.py` —— 业务逻辑，公开函数即对外接口
- [ ] 写 `router.py` —— `APIRouter`，路径以 `/api/ledger` 开头
- [ ] 写 `module.py` —— 声明模块名和路由前缀
- [ ] 在 `app/core/registry.py` 的模块清单里**加一行**
- [ ] 确认 `alembic/env.py` 能发现新模型（它遍历注册表导入各模块 models，见 9.1）
- [ ] 生成迁移并检查：`alembic revision --autogenerate -m "add ledger tables"` → 打开生成的脚本确认建表语句正确 → `alembic upgrade head`

### 8.2 前端

- [ ] 新建目录 `src/modules/ledger/`
- [ ] 写 `api.ts` —— 调用 `/api/ledger/*`，用 core 的 axios 实例
- [ ] 写 `stores/` —— 本模块的 Pinia store（如需要）
- [ ] 写 `views/` 和 `components/`
- [ ] 写 `routes.ts` —— 路径以 `ledger` 开头
- [ ] 写 `module.ts` —— 导航名称、图标、默认是否启用
- [ ] 在 `src/core/registry.ts` 的模块清单里**加一行**

### 8.3 验收（这一步才是关键）

- [ ] 启动后端，打开 `http://localhost:8000/docs`，确认新模块的接口全部出现
- [ ] 启动前端，确认首页导航出现新模块入口，点击能正常进入
- [ ] **跑 `git diff --stat` 看改动范围** —— 应该只有：新增的文件 + `registry.py` 一行 + `registry.ts` 一行
- [ ] **如果 diff 里出现了 `article/`、`plan/`、`ai/` 目录下的任何文件，说明边界破了**，回去检查是不是直接读了别人的表
- [ ] 提交：`git commit -m "feat(ledger): 新增记账模块"`

第三条验收是整套架构的核心价值所在。它把一个抽象的原则变成了一个可以反复执行的检查动作——**每次加模块都跑一遍，架构就不会悄悄腐化**。

## 九、风险与注意事项

| 类型 | 内容 | 应对建议 |
|------|------|----------|
| 风险 | **Alembic 自动生成迁移时看不到模块的表** | `alembic/env.py` 必须遍历注册表，把所有模块的 `models` 都 import 进来。SQLAlchemy 只有在模型被 import 过之后才知道它存在，这是新手最常见的坑 |
| 风险 | 前端路由懒加载配置不当，模块多了首屏变慢 | 模块级路由一律用 `() => import()`；不要把模块页面在 `main.ts` 里静态 import |
| 风险 | 开发时前端调不到后端接口 | `vite.config.ts` 里配 `/api` 代理指向 `http://localhost:8000`；生产环境由 FastAPI 托管静态文件，不需要代理 |
| 风险 | 生产环境下前端刷新页面出现 404 | FastAPI 要加 SPA 回退路由：非 `/api` 开头的路径一律返回 `index.html` |
| 风险 | 模块目录越写越厚，service.py 变成上千行 | 模块内部可以再拆文件（如 `service/` 包），只要 `service` 对外的函数签名不变，就不算破坏边界 |
| 风险 | 顺手在 core 里写业务代码 | 定期检查 core 目录，出现业务名词就搬回去。这条靠自觉，但代价最小、收益最大 |
| 风险 | **过度设计**：一开始就想做事件总线、依赖注入容器、插件协议 | 三个模块以内，显式 import 和显式注册表就是最优解。等真的疼了再改，现在做就是浪费 |

## 十、下一步

这份文档定的是"怎么组织"，还没有生成任何实际文件。接下来应该做的是：

1. **项目初始化配置**：按第三章的目录结构生成骨架文件，装好依赖，跑通"前端能调通一个后端接口"这条最小链路
2. **数据库设计**：把功能清单第四节的数据实体转成具体表结构和字段类型，产出 Alembic 的初始迁移

建议先做 1 再做 2——先把骨架立起来跑通，再往里填表结构，这样每一步都有可验证的结果。反过来先设计表，你会在一堆没有骨架的文件里迷路。
