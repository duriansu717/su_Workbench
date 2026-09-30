# Freedom Design 个人工作台

一个只有自己用的个人工作台：把生活中遇到的小问题写成文章沉淀下来，管理待办与计划，最终让这些文章变成一个可以提问的私人知识库。

设计上它是一个**可扩展的容器**——以后想到新功能，新增一个模块即可，不需要改动已有模块的代码。

## 文档

开发过程中的所有决策都记录在 `docs/` 下，按顺序阅读即为完整的推导链：

| 文档 | 回答的问题 |
|------|------------|
| [功能清单](docs/feature_list/feature_list.md) | 要做哪些功能 |
| [技术栈选型与版本控制](docs/tech_stack/tech_stack.md) | 用什么技术、什么版本、怎么管代码 |
| [架构设计](docs/architecture/architecture.md) | 代码怎么组织 |
| [数据库设计](docs/database/database.md) | 有哪些表、每个字段怎么定、为什么这么定 |
| [接口设计（文章模块）](docs/api_design/api_design.md) | 每个接口长什么样、字段有哪些、出错怎么返回 |
| [接口设计（计划模块）](docs/api_design/api_design_plan.md) | 同上，计划模块 |

## 环境要求

本机已具备，**无需额外安装任何环境**：

- Python 3.13.x
- Node.js 24.x + npm
- Git

数据库使用 Python 内置的 SQLite，不需要安装，也没有需要常驻后台的数据库服务。

## 启动

### 后端

```bash
cd backend
python -m venv .venv                      # 首次
source .venv/Scripts/activate             # Windows Git Bash（PowerShell 用 .venv\Scripts\Activate.ps1）
pip install -r requirements.txt           # 首次
cp .env.example .env                      # 首次，然后填入自己的 SECRET_KEY

python -m alembic upgrade head            # 首次：建表
python -m scripts.create_user             # 首次：创建登录账号（密码交互式输入）

uvicorn app.main:app --reload             # 默认 http://localhost:8000
```

> 装依赖卡住的话是网络问题，加国内镜像：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

**改过表结构之后**，重新生成并执行迁移：

```bash
python -m alembic revision --autogenerate -m "说明这次改了什么"
python -m alembic upgrade head
```

接口文档：<http://localhost:8000/docs>

### 前端

```bash
cd frontend
npm install                               # 首次
npm run dev                               # 默认 http://localhost:5173
```

开发时前端通过 Vite 代理把 `/api` 转发到后端 8000 端口，只需要启动这两个进程。

### 日常使用（不用开发服务器）

```bash
cd frontend && npm run build              # 构建静态文件
cd ../backend && uvicorn app.main:app     # FastAPI 直接托管，只跑一个进程
```

然后访问 <http://localhost:8000> 即可。

## 目录结构

```
freedom_design/
├── backend/
│   └── app/
│       ├── main.py            # 入口
│       ├── core/              # 骨架层：配置、数据库、认证、模块注册表
│       └── modules/           # 业务层：一个模块一个目录
├── frontend/
│   └── src/
│       ├── core/              # 骨架层：api、路由、注册表、布局
│       └── modules/           # 业务层
└── docs/                      # 各阶段产出文档
```

## 新增一个模块

见[架构设计文档](docs/architecture/architecture.md)第八章的完整清单。

要点：新增模块只应新增文件，外加在 `core/registry.py` 和 `src/core/registry.ts` 各加一行。**如果改到了已有模块目录下的文件，说明模块边界破了。**

## 备份

数据库是 `backend/data/` 下的单个文件，它不进 Git、没有版本历史。**请定期把整个 `data/` 目录复制到网盘或其他盘符**——这是唯一的备份手段。
