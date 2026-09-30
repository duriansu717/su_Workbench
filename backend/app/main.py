"""应用入口。

启动流程：建 FastAPI → 遍历模块注册表挂载路由 → 托管前端构建产物。

注意：**新增模块不需要改这个文件**。所有模块相关的动作都由注册表驱动。
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.core.registry import get_modules
from app.core.router import router as core_router

settings.ensure_directories()

app = FastAPI(title=settings.app_name)

# 开发时前端跑在 Vite 的 5173 端口，需要放行。
# 日常使用时前端由 FastAPI 自己托管，同源，这条配置不生效也没关系。
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- 骨架层自己的接口：健康检查 + 登录认证 ----
# 它们不经过模块注册表，因为认证是基础设施不是业务模块。
# 详见 core/router.py 顶部的说明。
app.include_router(core_router, prefix="/api")


# ---- 模块挂载：由注册表驱动，与具体模块无关 ----
for _module in get_modules():
    app.include_router(
        _module.router,
        prefix=_module.router_prefix,
        tags=[_module.name],
    )


# ---- 用户上传的文件 ----
# 这个目录是全局的（各模块往里写自己的子目录，如 images/），不属于任何模块，
# 所以在这里挂载而不是在模块里。文件内容本身在 .gitignore 里，不进版本库。
app.mount("/uploads", StaticFiles(directory=settings.upload_path), name="uploads")


# ---- 托管前端构建产物 ----
# 日常使用时先执行 `npm run build`，FastAPI 直接把前端一起托管，只需要跑一个进程。
# 开发时目录不存在，这一段会自动跳过，前端跑在 Vite 上。
_frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"

if _frontend_dist.is_dir():
    _assets = _frontend_dist / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str) -> FileResponse:
        """SPA 回退：非接口路径一律返回 index.html，交给前端路由处理。

        这条路由必须放在最后注册，否则会把上面的接口全部吃掉。
        """
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="接口不存在")
        return FileResponse(_frontend_dist / "index.html")
